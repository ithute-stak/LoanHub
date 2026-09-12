from __future__ import annotations

import base64
import html
import inspect
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any

import bleach
try:
    from bleach.css_sanitizer import CSSSanitizer
except ImportError:  # Bleach < 5 compatibility for older local environments.
    CSSSanitizer = None  # type: ignore[assignment]
from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document as WordDocument
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER, landscape
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Spacer,
    SimpleDocTemplate,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.company import LoanCompany
from database.models.workspace_document import WorkspaceDocument, WorkspaceDocumentAsset, WorkspaceDocumentSignature
from services.document_branding_service import get_company_branding_logos
from services.workspace_document_asset_service import active_signatures, asset_image_bytes, resolved_brand_asset


ALLOWED_TAGS = {
    "p", "div", "span", "br", "strong", "b", "em", "i", "u", "s", "strike",
    "h1", "h2", "h3", "h4", "blockquote", "ul", "ol", "li", "a", "hr",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "img", "sub", "sup",
    "code", "pre",
}
ALLOWED_ATTRIBUTES = {
    "*": [
        "class", "style", "data-page-break", "data-type", "data-paragraph-style",
        "data-signature-field", "data-field-id", "data-field-type", "data-label",
        "data-assigned-to", "data-required", "data-width", "data-height",
        "data-placeholder", "data-signed", "data-signed-by", "data-signed-at",
        "data-signature-method", "data-signature-asset-id", "data-verification-code",
    ],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}
ALLOWED_CSS_PROPERTIES = [
    "color", "background-color", "font-family", "font-size", "font-weight", "font-style",
    "text-decoration", "text-align", "line-height", "letter-spacing", "text-indent",
    "margin-left", "margin-right", "margin-top", "margin-bottom", "padding", "padding-left",
    "padding-right", "padding-top", "padding-bottom", "border", "border-color",
    "border-width", "border-style", "border-radius", "width", "max-width", "min-width",
    "height", "min-height", "max-height", "page-break-after", "page-break-before",
    "vertical-align", "white-space", "display",
]
CSS_SANITIZER = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES) if CSSSanitizer else None
BLEACH_CLEAN_PARAMETERS = frozenset(inspect.signature(bleach.clean).parameters)


def _attributes_without_inline_style() -> dict[str, list[str]]:
    """Return a copy of the allowlist with inline style removed.

    This is a safe fallback for Bleach releases that support neither
    ``css_sanitizer`` nor the legacy ``styles`` keyword.
    """
    return {
        tag: [attribute for attribute in attributes if attribute != "style"]
        for tag, attributes in ALLOWED_ATTRIBUTES.items()
    }


@dataclass(frozen=True)
class DocumentTheme:
    key: str
    accent: str
    heading: str
    soft: str
    body: str
    pdf_font: str
    word_font: str


THEMES: dict[str, DocumentTheme] = {
    "modern_blue": DocumentTheme("modern_blue", "#1268B3", "#0F2742", "#EDF6FF", "#172033", "Helvetica", "Arial"),
    "classic_word": DocumentTheme("classic_word", "#2F5597", "#1F3864", "#EAF0F8", "#1F1F1F", "Times-Roman", "Aptos"),
    "executive_navy": DocumentTheme("executive_navy", "#163A5F", "#102A43", "#E9F0F6", "#243B53", "Helvetica", "Arial"),
    "elegant_green": DocumentTheme("elegant_green", "#167D66", "#0E5546", "#E9F8F3", "#1E3A34", "Times-Roman", "Georgia"),
    "legal_monochrome": DocumentTheme("legal_monochrome", "#343A40", "#111827", "#F3F4F6", "#111827", "Times-Roman", "Times New Roman"),
    "warm_professional": DocumentTheme("warm_professional", "#A4552A", "#67351F", "#FFF4EC", "#3F3028", "Helvetica", "Arial"),
    "minimal_clean": DocumentTheme("minimal_clean", "#64748B", "#1E293B", "#F8FAFC", "#1E293B", "Helvetica", "Arial"),
}


def _theme(document: WorkspaceDocument) -> DocumentTheme:
    return THEMES.get(str(getattr(document, "style_key", "modern_blue")), THEMES["modern_blue"])




def _document_font_family(document: WorkspaceDocument) -> str:
    return str(getattr(document, "default_font_family", None) or "Arial")


def _document_font_size(document: WorkspaceDocument) -> int:
    try:
        return max(8, min(36, int(getattr(document, "default_font_size_pt", 11) or 11)))
    except (TypeError, ValueError):
        return 11


def _document_line_height(document: WorkspaceDocument) -> int:
    try:
        return max(90, min(250, int(getattr(document, "default_line_height_percent", 115) or 115)))
    except (TypeError, ValueError):
        return 115


def document_reference() -> str:
    return f"DOC-{uuid.uuid4().hex[:12].upper()}"


def user_display_name(user: Any) -> str:
    person = getattr(user, "person", None)
    return (
        getattr(person, "full_name", None)
        or " ".join(
            item
            for item in [getattr(person, "first_name", None), getattr(person, "last_name", None)]
            if item
        )
        or getattr(user, "email", None)
        or getattr(user, "phone", None)
        or "LoanHub user"
    )


def default_document_html(template_key: str, sender_name: str, template_context: dict[str, str] | None = None) -> str:
    """Return editable starter HTML for the document template gallery.

    Templates intentionally contain placeholders rather than customer data so a
    writer can safely duplicate and customise them. The Loan Agreement template
    mirrors the LoanHub/Filizwa-derived agreement structure already used by the
    lending contract generator, but remains an ordinary editable studio document.
    """
    sender = html.escape(sender_name or "Sender name")
    context = template_context or {}

    def value(key: str, fallback: str) -> str:
        return html.escape(str(context.get(key) or fallback))

    cv_header = (
        "<h1>[FULL NAME]</h1><p>[Professional title] · [Phone] · [Email] · [Location] · [LinkedIn / Portfolio]</p><hr>"
    )
    proposal_close = (
        "<h2>Acceptance</h2><p>[Acceptance conditions]</p>"
        "<p><strong>Prepared by:</strong> [Name / organisation]<br><strong>Date:</strong> [Date]</p>"
    )
    signature_pair = (
        "<div data-signature-field='true' data-field-id='borrower-signature' data-field-type='signature' "
        "data-label='Borrower signature' data-assigned-to='Borrower' data-required='true' data-width='100' "
        "data-height='62' data-placeholder='Sign here'></div>"
        "<div data-signature-field='true' data-field-id='lender-signature' data-field-type='signature' "
        "data-label='Lender representative signature' data-assigned-to='Lender' data-required='true' data-width='100' "
        "data-height='62' data-placeholder='Sign here'></div>"
    )

    templates: dict[str, str] = {
        "blank": "<p></p>",
        "formal_letter": (
            "<p style='text-align:right'>[Date]</p>"
            "<p><strong>[Recipient name]</strong><br>[Recipient title]<br>[Organisation]<br>[Postal or physical address]</p>"
            "<p>Dear [Title and surname],</p><h2 style='text-align:center'>RE: [LETTER SUBJECT]</h2>"
            "<p>Write the opening purpose of the letter here.</p>"
            "<p>Use additional paragraphs to provide important details, dates, references and the required action.</p>"
            "<p>Thank you for your attention to this matter.</p><p>Yours faithfully,</p>"
            f"<p><strong>{sender}</strong><br>[Position / role]<br>[Contact details]</p>"
        ),
        "client_confirmation_letter": (
            f"<p style='text-align:right'>{value('date', '[Date]')}</p>"
            f"<h1 style='text-align:center'>CLIENT CONFIRMATION LETTER OF {value('client_name', '[Client name]').upper()}</h1>"
            "<p>Dear Sir/Madam,</p>"
            f"<p>This letter confirms that {value('client_title', '[Title]')} <strong>{value('client_name', '[Client name]')}</strong>, "
            f"identity number <strong>{value('client_national_id', '[National ID]')}</strong>, is a client of "
            f"<strong>{value('company_name', '[Company name]')}</strong>.</p>"
            "<p>Our current LoanHub records show that the client has <strong>no overdue arrears</strong> with the company as at the date of this letter.</p>"
            f"<p>{value('credit_check_explanation', '[Explain any credit-check reporting delay here, if applicable.]')}</p>"
            "<p>For any further information regarding the above-mentioned client, please contact us.</p>"
            "<p>Yours sincerely,</p>"
            f"<p>________________________<br><strong>{value('signer_name', sender)}</strong><br>{value('signer_title', '[Manager / authorised representative]')}</p>"
        ),
        "good_standing_confirmation_letter": (
            f"<p style='text-align:right'>{value('date', '[Date]')}</p>"
            f"<h1 style='text-align:center'>CONFIRMATION LETTER OF {value('client_title', '[Title]')} {value('client_name', '[Client name]').upper()}</h1>"
            f"<p>This is to confirm that <strong>{value('client_title', '[Title]')} {value('client_name', '[Client name]')}</strong> "
            f"is a valued client of <strong>{value('company_name', '[Company name]')}</strong>.</p>"
            "<p>Our current records show that the client is in good standing and has no overdue arrears with us. "
            "The payment-history statement should be reviewed before making any stronger historical statement about missed payments.</p>"
            f"<p>{value('credit_check_explanation', '[Explain any credit-check reporting delay here, if applicable.]')}</p>"
            "<p>Kindly assist the client with the services requested.</p>"
            "<p><strong>THANK YOU.</strong></p>"
            f"<p>{value('signer_title', '[Director / Manager]')}<br>________________________<br><strong>{value('signer_name', sender)}</strong></p>"
        ),
        "paid_up_letter": (
            f"<p style='text-align:right'>{value('date', '[Date]')}</p>"
            f"<h1 style='text-align:center'>PAID-UP LETTER OF {value('client_name', '[Client name]').upper()}</h1>"
            f"<p>This letter confirms that <strong>{value('client_name', '[Client name]')}</strong>, identity number "
            f"<strong>{value('client_national_id', '[National ID]')}</strong>, was a borrower of "
            f"<strong>{value('company_name', '[Company name]')}</strong> under loan reference "
            f"<strong>{value('loan_reference', '[Loan reference]')}</strong> and has settled that debt in full.</p>"
            "<p>The LoanHub ledger balance for the selected loan is zero and there are no unpaid installments on that facility.</p>"
            f"<p>{value('credit_check_explanation', '[Explain any credit-check reporting delay here, if applicable.]')}</p>"
            "<p>Kindly assist the client with the services requested. For further enquiries regarding the above-mentioned individual, please contact us.</p>"
            "<p>Yours sincerely,</p>"
            f"<p>________________________<br><strong>{value('signer_name', sender)}</strong><br>{value('signer_title', '[Manager / authorised representative]')}</p>"
        ),
        "settlement_letter": (
            f"<p style='text-align:right'>{value('date', '[Date]')}</p>"
            f"<h1 style='text-align:center'>SETTLEMENT LETTER OF {value('client_name', '[Client name]').upper()}</h1>"
            "<p>Dear Sir/Madam,</p>"
            f"<p>This letter relates to the debt settlement arrangement between <strong>{value('company_name', '[Company name]')}</strong> and "
            f"<strong>{value('client_title', '[Title]')} {value('client_name', '[Client name]')}</strong>, identity number "
            f"<strong>{value('client_national_id', '[National ID]')}</strong>, for loan reference "
            f"<strong>{value('loan_reference', '[Loan reference]')}</strong>.</p>"
            f"<p>The current outstanding balance is <strong>{value('loan_balance', '[Outstanding balance]')}</strong>. "
            f"The scheduled installment amount is <strong>{value('loan_installment_amount', '[Installment amount]')}</strong>. "
            "Our current records show no overdue arrears on the selected facility as at the date of this letter.</p>"
            "<p>If the debtor fails to comply with a separately signed settlement agreement or payment arrangement, the terms of that agreement will apply. "
            "This confirmation does not replace the signed loan or settlement contract.</p>"
            f"<p>{value('credit_check_explanation', '[Explain any credit-check reporting delay here, if applicable.]')}</p>"
            "<p><strong>THIS LETTER IS VALID FOR 30 DAYS FROM THE DATE ABOVE.</strong></p>"
            f"<h2>Company bank account details</h2><p>{value('company_bank_accounts', '[Insert company bank account details]').replace(chr(10), '<br>')}</p>"
            "<p>Yours sincerely,</p>"
            f"<p>________________________<br><strong>{value('signer_name', sender)}</strong><br>{value('signer_title', '[Manager / authorised representative]')}</p>"
        ),
        "business_letter": (
            f"<p><strong>{sender}</strong><br>[Company / department]<br>[Address]<br>[Contact details]</p>"
            "<p style='text-align:right'>[Date]</p><p><strong>[Recipient]</strong><br>[Organisation]<br>[Address]</p>"
            "<p>Dear [Name],</p><h2>Business correspondence subject</h2>"
            "<p>Introduce the matter and desired outcome.</p><p>Provide supporting facts, commercial terms and dates.</p>"
            "<p>Sincerely,</p><p><strong>[Signatory name]</strong><br>[Title]</p>"
        ),
        "memo": (
            "<h1 style='text-align:center'>MEMORANDUM</h1><table><tbody>"
            f"<tr><th>From</th><td>{sender}</td></tr><tr><th>To</th><td>[Recipient / Department]</td></tr>"
            "<tr><th>Date</th><td>[Date]</td></tr><tr><th>Subject</th><td>[Memo subject]</td></tr></tbody></table>"
            "<p><strong>Purpose:</strong> Summarise the purpose of this memorandum.</p>"
            "<h2>Background</h2><p>Provide the necessary context and facts.</p>"
            "<h2>Decision / action required</h2><p>State the expected action, owner and deadline.</p>"
        ),
        "meeting_minutes": (
            "<h1 style='text-align:center'>MEETING MINUTES</h1><table><tbody>"
            "<tr><th>Meeting</th><td>[Meeting title]</td></tr><tr><th>Date and time</th><td>[Date and time]</td></tr>"
            "<tr><th>Venue / link</th><td>[Venue]</td></tr><tr><th>Chairperson</th><td>[Name]</td></tr>"
            "<tr><th>Minute taker</th><td>[Name]</td></tr></tbody></table>"
            "<h2>Attendance</h2><ul><li>[Attendee and role]</li></ul><h2>Agenda</h2><ol><li>[Agenda item]</li></ol>"
            "<h2>Discussion and resolutions</h2><table><thead><tr><th>Item</th><th>Discussion / decision</th><th>Owner</th><th>Due date</th></tr></thead>"
            "<tbody><tr><td>1</td><td>[Details]</td><td>[Name]</td><td>[Date]</td></tr></tbody></table>"
            "<h2>Next meeting</h2><p>[Date, time and place]</p>"
        ),
        "project_report": (
            "<h1>PROJECT REPORT</h1><p><strong>Project:</strong> [Project name]<br><strong>Reporting period:</strong> [Period]<br>"
            f"<strong>Prepared by:</strong> {sender}</p><h2>Executive summary</h2><p>Summarise progress, outcomes and major issues.</p>"
            "<h2>Objectives and scope</h2><p>[Objectives]</p><h2>Progress and deliverables</h2>"
            "<table><thead><tr><th>Deliverable</th><th>Status</th><th>Evidence</th><th>Next action</th></tr></thead>"
            "<tbody><tr><td>[Deliverable]</td><td>[Status]</td><td>[Evidence]</td><td>[Action]</td></tr></tbody></table>"
            "<h2>Risks and issues</h2><ul><li>[Risk and mitigation]</li></ul><h2>Recommendations</h2><p>[Recommendations]</p>"
        ),
        "proposal": (
            "<h1>EXECUTIVE SUMMARY</h1><p>[Brief overview, client need and value proposition]</p>"
            "<h1>BACKGROUND</h1><p>[Context and problem]</p><h1>PROPOSED SOLUTION</h1><p>[Detailed solution]</p>"
            "<h2>Scope and deliverables</h2><ul><li>[Deliverable]</li></ul>"
            "<h2>Implementation plan</h2><table><thead><tr><th>Phase</th><th>Activities</th><th>Timeline</th></tr></thead>"
            "<tbody><tr><td>1</td><td>[Activities]</td><td>[Timeline]</td></tr></tbody></table>"
            "<h2>Commercial proposal</h2><p>[Pricing and terms]</p>" + proposal_close
        ),
        "business_proposal": (
            "<h1>BUSINESS PROPOSAL</h1><h2>Opportunity</h2><p>[Business opportunity and customer pain point]</p>"
            "<h2>Objectives</h2><ul><li>[Objective]</li></ul><h2>Solution</h2><p>[Offering and differentiators]</p>"
            "<h2>Commercial model</h2><p>[Price, payment terms, ROI]</p><h2>Implementation</h2><p>[Plan and timeline]</p>"
            "<h2>Risk management</h2><p>[Key risks and controls]</p>" + proposal_close
        ),
        "technical_proposal": (
            "<h1>TECHNICAL PROPOSAL</h1><h2>1. Executive summary</h2><p>[Solution summary]</p>"
            "<h2>2. Requirements</h2><table><thead><tr><th>Requirement</th><th>Response</th><th>Evidence</th></tr></thead>"
            "<tbody><tr><td>[Requirement]</td><td>[Response]</td><td>[Evidence]</td></tr></tbody></table>"
            "<h2>3. Architecture and approach</h2><p>[Architecture]</p><h2>4. Security and compliance</h2><p>[Controls]</p>"
            "<h2>5. Delivery plan</h2><p>[Milestones]</p><h2>6. Support and SLA</h2><p>[Support model]</p>" + proposal_close
        ),
        "tender_proposal": (
            "<h1>TENDER RESPONSE</h1><h2>Bidder information</h2><p>[Legal name, registration, contacts]</p>"
            "<h2>Understanding of the requirement</h2><p>[Understanding]</p><h2>Methodology</h2><p>[Method]</p>"
            "<h2>Work plan</h2><table><thead><tr><th>Work package</th><th>Output</th><th>Duration</th><th>Owner</th></tr></thead>"
            "<tbody><tr><td>[Package]</td><td>[Output]</td><td>[Duration]</td><td>[Owner]</td></tr></tbody></table>"
            "<h2>Team and experience</h2><p>[Personnel and references]</p><h2>Financial proposal</h2><p>[Pricing]</p>" + proposal_close
        ),
        "funding_proposal": (
            "<h1>FUNDING PROPOSAL</h1><h2>Organisation profile</h2><p>[Mission, history and governance]</p>"
            "<h2>Problem statement</h2><p>[Need]</p><h2>Project goal and outcomes</h2><ul><li>[Outcome]</li></ul>"
            "<h2>Activities and implementation</h2><p>[Activities]</p><h2>Monitoring and evaluation</h2><p>[Indicators]</p>"
            "<h2>Budget</h2><table><thead><tr><th>Item</th><th>Amount</th><th>Justification</th></tr></thead>"
            "<tbody><tr><td>[Item]</td><td>LSL 0.00</td><td>[Reason]</td></tr></tbody></table><h2>Sustainability</h2><p>[Plan]</p>" + proposal_close
        ),
        "partnership_proposal": (
            "<h1>PARTNERSHIP PROPOSAL</h1><h2>Partnership vision</h2><p>[Shared opportunity]</p>"
            "<h2>Parties and strengths</h2><p>[Capabilities]</p><h2>Proposed collaboration model</h2><p>[Roles and operating model]</p>"
            "<h2>Commercial and resource contribution</h2><p>[Contributions]</p><h2>Governance</h2><p>[Decision making]</p>"
            "<h2>Next steps</h2><ol><li>[Action]</li></ol>" + proposal_close
        ),
        "policy": (
            "<h1 style='text-align:center'>[POLICY NAME]</h1><table><tbody><tr><th>Policy owner</th><td>[Owner]</td></tr>"
            "<tr><th>Effective date</th><td>[Date]</td></tr><tr><th>Review date</th><td>[Date]</td></tr><tr><th>Version</th><td>1.0</td></tr></tbody></table>"
            "<h2>1. Purpose</h2><p>[Purpose]</p><h2>2. Scope</h2><p>[Who and what the policy applies to]</p>"
            "<h2>3. Definitions</h2><p>[Definitions]</p><h2>4. Policy statements</h2><ol><li>[Policy requirement]</li></ol>"
            "<h2>5. Responsibilities</h2><p>[Responsibilities]</p><h2>6. Monitoring and review</h2><p>[Monitoring process]</p>"
            "<h2>7. Approval</h2><p>[Approval details]</p>"
        ),
        "contract": (
            "<h1 style='text-align:center'>AGREEMENT</h1><p>This agreement is made on <strong>[Date]</strong> between:</p>"
            "<p><strong>1. [Party A legal name]</strong>, of [address] (\"Party A\"); and</p>"
            "<p><strong>2. [Party B legal name]</strong>, of [address] (\"Party B\").</p>"
            "<h2>1. Purpose</h2><p>[Purpose of agreement]</p><h2>2. Obligations</h2><p>[Obligations]</p>"
            "<h2>3. Payment and consideration</h2><p>[Payment terms]</p><h2>4. Term and termination</h2><p>[Term]</p>"
            "<h2>5. Confidentiality</h2><p>[Confidentiality terms]</p><h2>6. Dispute resolution</h2><p>[Process]</p>"
            "<h2>7. General</h2><p>[Notices, amendments, governing law and severability]</p><p>The parties indicate acceptance by signing below.</p>" + signature_pair
        ),
        "service_agreement": (
            "<h1>SERVICE AGREEMENT</h1><p>Between <strong>[Service Provider]</strong> and <strong>[Client]</strong>, effective [Date].</p>"
            "<h2>1. Services</h2><p>[Scope]</p><h2>2. Deliverables and service levels</h2><p>[Deliverables/SLA]</p>"
            "<h2>3. Fees and payment</h2><p>[Fees]</p><h2>4. Client responsibilities</h2><p>[Responsibilities]</p>"
            "<h2>5. Confidentiality and data protection</h2><p>[Terms]</p><h2>6. Intellectual property</h2><p>[Ownership/licence]</p>"
            "<h2>7. Term, suspension and termination</h2><p>[Terms]</p><h2>8. Liability and dispute resolution</h2><p>[Terms]</p>" + signature_pair
        ),
        "employment_contract": (
            "<h1>EMPLOYMENT AGREEMENT</h1><p>Employer: <strong>[Employer]</strong><br>Employee: <strong>[Employee]</strong><br>Start date: [Date]</p>"
            "<h2>1. Position and duties</h2><p>[Title, reporting line, duties]</p><h2>2. Place and hours of work</h2><p>[Details]</p>"
            "<h2>3. Remuneration and benefits</h2><p>[Salary, benefits, deductions]</p><h2>4. Leave</h2><p>[Leave]</p>"
            "<h2>5. Conduct, confidentiality and company property</h2><p>[Terms]</p><h2>6. Performance and discipline</h2><p>[Terms]</p>"
            "<h2>7. Termination</h2><p>[Notice and procedures]</p><h2>8. General</h2><p>[Applicable law and complete agreement]</p>" + signature_pair
        ),
        "nda": (
            "<h1>NON-DISCLOSURE AGREEMENT</h1><p>This NDA is entered into between [Disclosing Party] and [Receiving Party] on [Date].</p>"
            "<h2>1. Confidential information</h2><p>[Definition]</p><h2>2. Permitted purpose</h2><p>[Purpose]</p>"
            "<h2>3. Receiving party obligations</h2><p>[Security and non-disclosure]</p><h2>4. Exclusions</h2><p>[Exclusions]</p>"
            "<h2>5. Return or destruction</h2><p>[Requirements]</p><h2>6. Term and remedies</h2><p>[Term/remedies]</p>" + signature_pair
        ),
        "consultancy_agreement": (
            "<h1>CONSULTANCY AGREEMENT</h1><p>Client: [Client]<br>Consultant: [Consultant]<br>Effective date: [Date]</p>"
            "<h2>1. Engagement and scope</h2><p>[Services]</p><h2>2. Deliverables and timeline</h2><p>[Deliverables]</p>"
            "<h2>3. Fees, expenses and taxes</h2><p>[Commercial terms]</p><h2>4. Independent contractor status</h2><p>[Status]</p>"
            "<h2>5. Confidentiality and intellectual property</h2><p>[Terms]</p><h2>6. Termination</h2><p>[Terms]</p>"
            "<h2>7. Liability and dispute resolution</h2><p>[Terms]</p>" + signature_pair
        ),
        "partnership_agreement": (
            "<h1>PARTNERSHIP AGREEMENT</h1><p>Partners: [Partner A], [Partner B], [Additional partners]</p>"
            "<h2>1. Purpose and business</h2><p>[Purpose]</p><h2>2. Contributions and ownership</h2><p>[Capital/assets]</p>"
            "<h2>3. Management and voting</h2><p>[Governance]</p><h2>4. Profits, losses and distributions</h2><p>[Terms]</p>"
            "<h2>5. Banking and records</h2><p>[Controls]</p><h2>6. Admission, withdrawal and dissolution</h2><p>[Terms]</p>"
            "<h2>7. Confidentiality and dispute resolution</h2><p>[Terms]</p>" + signature_pair
        ),
        "loan_agreement": (
            "<h1 style='text-align:center'>LOAN AGREEMENT</h1>"
            "<p style='text-align:center'><strong>CONDITIONS OF LOAN, COST OF CREDIT AND REPAYMENT TERMS</strong></p>"
            "<table><tbody><tr><th>Agreement number</th><td>[Agreement number]</td><th>Loan account</th><td>[Loan reference]</td></tr>"
            "<tr><th>Application reference</th><td>[Application reference]</td><th>Agreement date</th><td>[Date]</td></tr></tbody></table>"
            "<h2>PARTIES</h2><table><tbody><tr><th>Lender</th><td>[Lender legal name, registration, licence, address and contact]</td></tr>"
            "<tr><th>Borrower</th><td>[Borrower full name, national ID, address and contact]</td></tr></tbody></table>"
            "<p><strong>IMPORTANT:</strong> Read the full agreement, cost disclosure and repayment schedule before signing. Do not sign while required information is blank.</p>"
            "<h2>1. CONDITIONS OF LOAN</h2><table><tbody><tr><th>1.1 Loan amount</th><td>LSL [0.00]</td><th>1.2 Number of instalments</th><td>[Number]</td></tr>"
            "<tr><th>1.3 Instalment amount</th><td>LSL [0.00]</td><th>1.4 Instalments payable</th><td>[Frequency]</td></tr>"
            "<tr><th>1.5 First instalment</th><td>[Date]</td><th>1.6 Last instalment</th><td>[Date]</td></tr></tbody></table>"
            "<h2>2. COST ELEMENTS OF THE LOAN</h2><table><tbody><tr><th>2.1 Interest charged</th><td>LSL [0.00]</td></tr>"
            "<tr><th>2.2 Initiation / processing fee</th><td>LSL [0.00]</td></tr><tr><th>2.3 Service and schedule fees</th><td>LSL [0.00]</td></tr>"
            "<tr><th>2.4 Taxes included</th><td>LSL [0.00]</td></tr><tr><th>2.5 Total charge of credit</th><td>LSL [0.00]</td></tr>"
            "<tr><th>3. Approved interest rate</th><td>[Rate]%</td></tr><tr><th>4. Total amount added</th><td>LSL [0.00]</td></tr>"
            "<tr><th>5. Total amount repayable</th><td>LSL [0.00]</td></tr></tbody></table>"
            "<h2>6. Credit charges and payment schedule</h2><p>The cost disclosure, Key Facts Statement and repayment schedule form part of this agreement and must be read together with these conditions.</p>"
            "<h2>7. Early settlement</h2><p>The borrower may settle this agreement at any time by paying the unpaid principal, accrued disclosed interest, disclosed fees and any other lawful amount up to the settlement date.</p>"
            "<h2>8. Proposed loan agreement and inconsistencies</h2><p>This document, together with the cost disclosure and repayment schedule, constitutes the proposed loan agreement. No undisclosed fee or charge may be collected.</p>"
            "<h2>9. Interest rate</h2><p>Interest is calculated on the outstanding principal using the approved rate and recorded calculation method. Any permitted rate change must follow applicable law and required notice.</p>"
            "<h2>10. Settlement of the loan and payment mandate</h2><p>The borrower agrees to repay using the approved payment method. Any debit-order, bank, salary or mobile-money mandate forms an annexure where applicable.</p>"
            "<h2>11. Penalty clause</h2><p>Only penalties, service fees and reasonable recovery costs properly disclosed, agreed and permitted by law may be charged.</p>"
            "<h2>12. Lender's right to terminate or enforce</h2><p>Default and recovery action must follow lawful notice, enforcement and credit-reporting procedures.</p>"
            "<h2>13. Document provided and available</h2><p>A completed copy of the signed agreement and repayment schedule must be provided or securely made available to the borrower without charge.</p>"
            "<h2>14. Conditions, rights and obligations</h2><p>The parties' rights and obligations are governed by this agreement, signed annexures and mandatory laws of the Kingdom of Lesotho.</p>"
            "<h2>15. Account statements</h2><p>The lender must provide statements at legally required intervals and on reasonable request.</p>"
            "<h2>16. Administration, insolvency or similar order</h2><p>The borrower must disclose any relevant administration, insolvency, debt-relief or similar process and notify the lender if one begins later.</p>"
            "<h2>17. Debt review or repayment arrangement</h2><p>Any existing review, restructuring or repayment arrangement must be disclosed and any revised arrangement should be affordable and recorded in writing.</p>"
            "<h2>18. Dispute resolution</h2><p>The borrower should first raise a dispute with the lender. If unresolved, the borrower may approach the Central Bank of Lesotho, another competent regulator, an available ombudsman or a court with jurisdiction.</p>"
            "<h2>19. PRIVACY, NOTICES AND GENERAL TERMS</h2><p>Personal information must be protected and used only for lawful lending, administration, fraud prevention, compliance, collection and authorised credit reporting. Notices use the addresses recorded in this agreement. Written amendments and signed annexures form part of the complete agreement.</p>"
            "<h2>ANNEXURE A - REPAYMENT SCHEDULE</h2><table><thead><tr><th>Instalment</th><th>Due date</th><th>Principal</th><th>Interest</th><th>Fees</th><th>Total</th></tr></thead>"
            "<tbody><tr><td>1</td><td>[Date]</td><td>LSL [0.00]</td><td>LSL [0.00]</td><td>LSL [0.00]</td><td>LSL [0.00]</td></tr></tbody></table>"
            "<h2>ANNEXURE B - ACCEPTANCE AND SIGNATURES</h2><p>By signing, each signatory confirms that the disclosed terms were read or explained and that the signature is intended to authenticate this agreement.</p>" + signature_pair
        ),
        "loan_agreement_filizwa_style": (
            "<p style='text-align:center; margin:0'>Client number: [Client number] &nbsp;&nbsp;&nbsp; Loan number: [Loan number]</p>"
            "<h1 style='text-align:center; margin:4px 0 0 0'>LOAN AGREEMENT</h1>"
            "<p style='text-align:center; margin:0 0 10px 0'><strong>[LENDER NAME]</strong> [The Lender]</p>"
            "<table><tbody>"
            "<tr><th style='width:35%'>SURNAME [Mr. / Mrs. / Ms.]</th><td style='width:35%'>[Borrower surname]</td><td style='width:30%'>[The Borrower]</td></tr>"
            "<tr><th>FIRST NAMES</th><td colspan='2'>[Borrower first names]</td></tr>"
            "<tr><th>ID NUMBER</th><td>[Borrower ID number]</td><th>TEL No: [Phone] &nbsp;&nbsp; E-mail address: [Email]</th></tr>"
            "<tr><th>ADDRESS</th><td colspan='2'>"
            "The Borrower nominates the following address for purposes of mail of any nature, including legal notices and court orders, to be sent:<br>"
            "[Address line 1]<br>[Address line 2]<br>[Town / city]<br>Postal Code: [Postal code]<br><br>"
            "If the above address of the Borrower changes, then the Borrower must notify the Lender of the new address in writing by hand or registered mail to the address of the Lender within 10 business days from change."
            "</td></tr></tbody></table>"
            "<h2 style='text-align:center'>1. CONDITIONS OF LOAN</h2>"
            "<table><tbody>"
            "<tr><th>1.1 Loan amount</th><td>LSL [1,000.00]</td><th>1.2 Number of Instalments</th><td>[1]</td><th>1.3 Instalment Amount</th><td>LSL [1,223.01]</td></tr>"
            "<tr><th>1.4 Instalments payable monthly / weekly / fortnightly</th><td>[MONTHLY]</td><th>1.5 Date first instalment payable</th><td>[15/04/2026]</td><th>1.6 Date last instalment payable</th><td>[15/04/2026]</td></tr>"
            "</tbody></table>"
            "<h2 style='text-align:center'>2. COST ELEMENTS OF LOAN</h2>"
            "<table><tbody>"
            "<tr><th>2.1 Amount of Interest Charged</th><td>LSL [33.33]</td></tr>"
            "<tr><th>2.2 Initiation Fee</th><td>LSL [150.00]</td></tr>"
            "<tr><th>2.3 Total Monthly Service Fee</th><td>LSL [39.68]</td></tr>"
            "<tr><th>2.4 Value Added Tax on Initiation Fee and Total Monthly Service Fee</th><td>LSL [0.00]</td></tr>"
            "<tr><th>2.5 RAND VALUE OF TOTAL CHARGE OF CREDIT [2.1 TO 2.4]</th><td>LSL [223.01]</td></tr>"
            "<tr><th>Interest Rate of Small Loan</th><td>[5.00]</td></tr>"
            "</tbody></table>"
            "<table><tbody>"
            "<tr><th>4. TOTAL AMOUNT TO BE ADDED TO LOAN AMOUNT</th><td>LSL [223.01]</td></tr>"
            "<tr><th>5. TOTAL AMOUNT REPAYABLE [1.1+4]</th><td>LSL [1,223.01]</td></tr>"
            "</tbody></table>"
            "<p><strong>6. Credit Charges &amp; Payment Schedule:</strong> Subject to paragraph 8.2, the payment schedule and credit charges included in the Pre-Agreement Statement &amp; Quotation form part of this agreement and are considered to be included as such in this agreement.</p>"
            "<p><strong>7. Early Settlement:</strong> The Borrower may settle this agreement at any time by paying the unpaid balance of the loan amount and unpaid interest charges and all other fees and charges up to the date of Settlement.</p>"
            "<p><strong>8. Proposed Loan Agreement:</strong></p>"
            "<p><strong>8.1.</strong> This document together with Pre-Agreement Statement &amp; Quotation provided serves as a proposed loan agreement and if the Borrower elects to enter into this agreement with the Lender, the agreement should be concluded at or below the interest rate and costs initially quoted in the Pre-Agreement Statement and Quotation. The Borrower has the right to enter into this loan agreement at any stage prior to the lapse of the five (5) business day period.</p>"
            "<p><strong>8.2.</strong> Should any inconsistencies exist in relation to credit charges between the Pre-Agreement Statement &amp; Quotation and the calculation of any credit costs or charges contained in this agreement, the calculations recorded in this agreement will prevail provided that such credit charges are less than the charges contained in the Pre-Agreement Statement &amp; Quotation.</p>"
            "<p><strong>9. Interest Rate:</strong> The interest rates for small and unsecured micro-loans are calculated in arrears on the outstanding capital at a fixed rate as per applicable law and regulations. Should a change of interest rate occur as contemplated by law that affects this agreement, the Borrower will be given five (5) business days written notice before the change is implemented.</p>"
            "<p><strong>10. Settlement of Loan:</strong> The Borrower is hereby notified and agrees that this loan will be settled by making charges against the bank account specified hereunder. The details of the charges are set out in the conditions of this loan which form part of this agreement:</p>"
            "<table><tbody>"
            "<tr><th>Name of Bank Account</th><td>[Borrower bank account name]</td><th>Account Number</th><td>[Account number]</td></tr>"
            "<tr><th>Bank</th><td>[Bank name]</td><th>Branch Code</th><td>[Branch code]</td></tr>"
            "<tr><th>Deduction Amount</th><td>[As per clause 1.3]</td><th>Date(s) of Deductions</th><td>[As per clauses 1.5 and 1.6]</td></tr>"
            "</tbody></table>"
            "<p><strong>11. Penalty Clause:</strong> In the event of default for whatever reason penalty interest and penalty service fee on repayments in arrears will be charged at the same interest rate and service fee rate set for this agreement. All attorney's or registered debt collectors' costs will also be recovered from the Borrower on the attorney and client scale or on the official tariffs applicable to registered debt collectors, as the case may be.</p>"
            "<p><strong>12. Lender's right to terminate agreement:</strong> The Lender reserves the right to terminate this agreement with the Borrower if the Borrower defaults with any of the agreed repayments and to proceed with legal enforcement processes which may result in a Court of Law enforcing the repayment of the Borrower's outstanding obligations.</p>"
            "<p><strong>13. Document provided and available:</strong> A copy of this signed Loan agreement is provided to the Borrower free of charge. A copy of the Act and Regulations is available to the Borrower to peruse the sections stated in this agreement and others on the premises of the Lender.</p>"
            "<p><strong>14. Conditions, Rights and Obligations:</strong> The Borrower and Lender agree that their rights and obligations under this agreement are limited to the conditions and clauses of this agreement as well as the conditions and requirements set in the applicable law.</p>"
            "<p><strong>15. Account Statements:</strong> The Lender will provide an account statement free of charge to the Borrower at the end of every third month during the term of a loan agreement. Account statements during intermediate months will be provided on request at the applicable cost per page.</p>"
            "<p><strong>16. Administration Order:</strong> The Borrower declares that he / she is presently not under administration, has no intention of being placed under administration and agrees that he / she will not attempt to be placed under administration prior to discussing his / her financial situation with the Lender.</p>"
            "<p><strong>17. Debt review/re-arrangement:</strong> The Borrower declares that at the signing of this agreement he / she has not applied for debt review or a similar debt rearrangement process, and is not under debt re-arrangement, unless explicitly disclosed.</p>"
            "<p><strong>18. Dispute Resolution:</strong> The Borrower agrees that in the event of any dispute or uncertainty he / she will discuss the matter with the Lender as a first step to resolve the issue. If the matter is not resolved to his / her satisfaction, the Borrower may submit the matter in writing and escalate it to the appropriate regulator or authority.</p>"
            "<h2>CONDITIONS ACCEPTED BY BORROWER</h2>"
            "<p>Signed at [Place] on the [Date].</p>"
            "<table style='margin-bottom:14px'><tbody><tr>"
            "<td style='width:50%; border:none'>"
            "<div data-signature-field='true' data-field-id='borrower-signature' data-field-type='signature' data-label='Borrower signature' data-assigned-to='Borrower' data-required='true' data-width='100' data-height='62' data-placeholder='Borrower signs here'></div>"
            "<p style='text-align:center'>________________________<br>BORROWER</p>"
            "</td>"
            "<td style='width:50%; border:none'><p style='text-align:center; padding-top:55px'>________________________<br>WITNESS</p></td>"
            "</tr></tbody></table>"
            "<h2>CONDITIONS ACCEPTED BY LENDER</h2>"
            "<p>Signed at [Place] on the [Date].</p>"
            "<table><tbody><tr>"
            "<td style='width:50%; border:none'>"
            "<div data-signature-field='true' data-field-id='lender-signature' data-field-type='signature' data-label='Lender signature' data-assigned-to='Lender' data-required='true' data-width='100' data-height='62' data-placeholder='Lender signs here'></div>"
            "<p style='text-align:center'>________________________<br>LENDER</p>"
            "</td>"
            "<td style='width:50%; border:none'><p style='text-align:center; padding-top:55px'>________________________<br>WITNESS</p></td>"
            "</tr></tbody></table>"
        ),
        "invoice": (
            "<h1 style='text-align:right'>INVOICE</h1><table><tbody><tr><th>Invoice number</th><td>[Number]</td><th>Date</th><td>[Date]</td></tr>"
            "<tr><th>Due date</th><td>[Date]</td><th>Currency</th><td>LSL</td></tr></tbody></table>"
            "<h2>Bill to</h2><p><strong>[Customer]</strong><br>[Address]<br>[Contact]</p>"
            "<table><thead><tr><th>Description</th><th>Quantity</th><th>Rate</th><th>Amount</th></tr></thead>"
            "<tbody><tr><td>[Service / item]</td><td>1</td><td>LSL 0.00</td><td>LSL 0.00</td></tr>"
            "<tr><th colspan='3' style='text-align:right'>Total</th><th>LSL 0.00</th></tr></tbody></table>"
            "<h2>Payment details</h2><p>[Bank or mobile-money details and payment reference]</p><p>[Terms and notes]</p>"
        ),
        "certificate": (
            "<p style='text-align:center;font-size:14pt'>CERTIFICATE OF</p><h1 style='text-align:center;font-size:32pt'>[ACHIEVEMENT / COMPLETION]</h1>"
            "<p style='text-align:center;font-size:14pt'>This certificate is proudly presented to</p>"
            "<h2 style='text-align:center;font-size:24pt'>[RECIPIENT NAME]</h2><p style='text-align:center'>For [achievement, programme or service].</p>"
            "<p style='text-align:center'>Awarded on [date] at [place].</p><p><br></p>"
        ),
        "resume": cv_header + (
            "<h2>Professional profile</h2><p>[Concise professional summary]</p><h2>Core skills</h2><ul><li>[Skill]</li></ul>"
            "<h2>Experience</h2><p><strong>[Role]</strong> — [Organisation]<br>[Dates]</p><ul><li>[Achievement with measurable impact]</li></ul>"
            "<h2>Education</h2><p><strong>[Qualification]</strong> — [Institution], [Year]</p><h2>References</h2><p>Available on request.</p>"
        ),
        "executive_cv": cv_header + (
            "<h2>Executive profile</h2><p>[Leadership summary, industries, scale and impact]</p><h2>Leadership competencies</h2><ul><li>[Competency]</li></ul>"
            "<h2>Career experience</h2><p><strong>[Executive role]</strong> — [Organisation] | [Dates]</p><ul><li>[Strategic achievement with metrics]</li></ul>"
            "<h2>Board / governance experience</h2><p>[Board roles]</p><h2>Education and executive development</h2><p>[Qualifications]</p><h2>Selected recognition</h2><p>[Awards]</p>"
        ),
        "software_cv": cv_header + (
            "<h2>Summary</h2><p>[Full-stack / engineering profile]</p><h2>Technical stack</h2><p><strong>Languages:</strong> [Languages]<br><strong>Frameworks:</strong> [Frameworks]<br><strong>Cloud & tools:</strong> [Tools]</p>"
            "<h2>Experience</h2><p><strong>[Role]</strong> — [Company] | [Dates]</p><ul><li>[Technical achievement]</li></ul>"
            "<h2>Selected projects</h2><p><strong>[Project]</strong> — [Stack]</p><ul><li>[Problem, solution and measurable outcome]</li></ul>"
            "<h2>Education & certifications</h2><p>[Details]</p><h2>Links</h2><p>[GitHub] · [Portfolio]</p>"
        ),
        "graduate_cv": cv_header + (
            "<h2>Career objective</h2><p>[Target role and strengths]</p><h2>Education</h2><p><strong>[Qualification]</strong> — [Institution] | [Year]</p>"
            "<h2>Academic projects</h2><p><strong>[Project]</strong></p><ul><li>[Contribution/result]</li></ul><h2>Internship / volunteer experience</h2><p>[Experience]</p>"
            "<h2>Skills</h2><ul><li>[Skill]</li></ul><h2>Achievements and activities</h2><p>[Details]</p><h2>References</h2><p>[Reference or available on request]</p>"
        ),
        "academic_cv": cv_header + (
            "<h2>Research profile</h2><p>[Fields and research interests]</p><h2>Education</h2><p>[Degrees]</p><h2>Academic appointments</h2><p>[Appointments]</p>"
            "<h2>Publications</h2><ol><li>[Citation]</li></ol><h2>Research projects and grants</h2><p>[Projects]</p><h2>Teaching</h2><p>[Courses]</p>"
            "<h2>Conferences and presentations</h2><p>[Presentations]</p><h2>Professional service</h2><p>[Service]</p>"
        ),
        "skills_cv": cv_header + (
            "<h2>Profile</h2><p>[Short profile]</p><h2>Key capabilities</h2><table><tbody><tr><th>[Capability]</th><td>[Evidence / years / level]</td></tr></tbody></table>"
            "<h2>Selected achievements</h2><ul><li>[Achievement]</li></ul><h2>Employment history</h2><p><strong>[Role]</strong> — [Organisation] | [Dates]</p>"
            "<h2>Qualifications</h2><p>[Qualifications]</p><h2>Professional memberships</h2><p>[Memberships]</p>"
        ),
    }
    return templates.get(template_key, templates["formal_letter"])

def strip_legacy_filizwa_placeholder_header(value: str | None) -> str:
    """Remove the obsolete editable logo/company placeholder table.

    The branding header is now rendered by Document Studio from the current
    company and logo assets. Existing documents created before that change may
    still contain the old three-column placeholder table in stored HTML.
    """
    raw = str(value or "")
    if not all(marker in raw for marker in ("[LEFT LOGO]", "[COMPANY NAME]", "[RIGHT LOGO]")):
        return raw

    soup = BeautifulSoup(raw, "html.parser")
    for table in list(soup.find_all("table")):
        text = " ".join(table.stripped_strings)
        if all(marker in text for marker in ("[LEFT LOGO]", "[COMPANY NAME]", "[RIGHT LOGO]")):
            table.decompose()

    return "".join(str(node) for node in soup.contents)


def sanitize_document_html(value: str | None) -> str:
    raw = strip_legacy_filizwa_placeholder_header(value)[:2_500_000]
    options: dict[str, Any] = {
        "tags": ALLOWED_TAGS,
        "attributes": ALLOWED_ATTRIBUTES,
        "protocols": {"http", "https", "mailto", "tel", "data"},
        "strip": True,
    }

    if CSS_SANITIZER is not None and "css_sanitizer" in BLEACH_CLEAN_PARAMETERS:
        options["css_sanitizer"] = CSS_SANITIZER
    elif "styles" in BLEACH_CLEAN_PARAMETERS:
        # Compatibility with old Bleach versions only.
        options["styles"] = ALLOWED_CSS_PROPERTIES
    else:
        # Never pass unsupported keywords. Removing inline style is safer than
        # failing the request or accepting unsanitised CSS.
        options["attributes"] = _attributes_without_inline_style()

    return bleach.clean(raw, **options)


def plain_text_from_html(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for field in soup.select("[data-signature-field]"):
        label = field.get("data-label") or "Signature field"
        field.replace_with(f"[{label}]")
    return soup.get_text("\n", strip=True)[:1_000_000]


def signature_field_count(value: str | None) -> int:
    return len(BeautifulSoup(value or "", "html.parser").select("[data-signature-field]"))


def signature_field_metadata(value: str | None) -> dict[str, dict[str, str]]:
    fields: dict[str, dict[str, str]] = {}
    for node in BeautifulSoup(value or "", "html.parser").select("[data-signature-field]"):
        field_id = str(node.get("data-field-id") or "").strip()
        if not field_id:
            continue
        fields[field_id] = {
            "field_type": str(node.get("data-field-type") or "signature"),
            "assigned_to": str(node.get("data-assigned-to") or "Any signer"),
            "label": str(node.get("data-label") or "Signature"),
        }
    return fields


def content_json_or_default(value: dict[str, Any] | None) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {"type": "doc", "content": []}


def _style_value(tag: Tag, name: str) -> str | None:
    style = str(tag.get("style") or "")
    match = re.search(rf"(?:^|;)\s*{re.escape(name)}\s*:\s*([^;]+)", style, re.I)
    return match.group(1).strip() if match else None


def _css_number(value: str | None, *, default: float = 0.0) -> float:
    if not value:
        return default
    match = re.match(r"\s*(-?[0-9.]+)", value)
    return float(match.group(1)) if match else default


def _font_size_pt(value: str | None, default: float) -> float:
    if not value:
        return default
    number = _css_number(value, default=default)
    if value.lower().strip().endswith("px"):
        number *= 0.75
    return min(72.0, max(6.0, number))


def _data_image(src: str | None) -> bytes | None:
    if not src or not src.startswith("data:image/") or "," not in src:
        return None
    header, encoded = src.split(",", 1)
    if ";base64" not in header:
        return None
    try:
        payload = base64.b64decode(encoded, validate=True)
    except Exception:
        return None
    return payload if len(payload) <= 3 * 1024 * 1024 else None


def _pdf_font_name(font_family: str | None, *, bold: bool = False, italic: bool = False) -> str:
    family = (font_family or "").lower()
    if "times" in family or "georgia" in family or "serif" in family:
        base = "Times"
        if bold and italic:
            return "Times-BoldItalic"
        if bold:
            return "Times-Bold"
        if italic:
            return "Times-Italic"
        return "Times-Roman"
    if "courier" in family or "mono" in family:
        if bold and italic:
            return "Courier-BoldOblique"
        if bold:
            return "Courier-Bold"
        if italic:
            return "Courier-Oblique"
        return "Courier"
    if bold and italic:
        return "Helvetica-BoldOblique"
    if bold:
        return "Helvetica-Bold"
    if italic:
        return "Helvetica-Oblique"
    return "Helvetica"


def _reportlab_inline(tag: Tag | NavigableString, inherited: dict[str, Any] | None = None) -> str:
    inherited = dict(inherited or {})
    if isinstance(tag, NavigableString):
        text = html.escape(str(tag))
        if not text:
            return ""
        font = inherited.get("font")
        size = inherited.get("size")
        color = inherited.get("color")
        attrs = []
        if font:
            attrs.append(f'name="{font}"')
        if size:
            attrs.append(f'size="{size}"')
        if color:
            attrs.append(f'color="{color}"')
        return f"<font {' '.join(attrs)}>{text}</font>" if attrs else text

    name = tag.name.lower()
    if name in {"strong", "b"}:
        inherited["bold"] = True
    if name in {"em", "i"}:
        inherited["italic"] = True
    family = _style_value(tag, "font-family")
    if family:
        inherited["font"] = _pdf_font_name(family, bold=inherited.get("bold", False), italic=inherited.get("italic", False))
    size = _style_value(tag, "font-size")
    if size:
        inherited["size"] = _font_size_pt(size, 10)
    color = _style_value(tag, "color")
    if color and re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        inherited["color"] = color

    inner = "".join(_reportlab_inline(child, inherited) for child in tag.children)
    if name in {"strong", "b"}:
        return f"<b>{inner}</b>"
    if name in {"em", "i"}:
        return f"<i>{inner}</i>"
    if name == "u":
        return f"<u>{inner}</u>"
    if name == "br":
        return "<br/>"
    if name in {"sub", "sup"}:
        return f"<{name}>{inner}</{name}>"
    if name == "code":
        return f'<font name="Courier">{inner}</font>'
    return inner


def _alignment(tag: Tag) -> int:
    value = (_style_value(tag, "text-align") or "left").lower()
    return {"center": TA_CENTER, "right": TA_RIGHT, "justify": TA_JUSTIFY}.get(value, TA_LEFT)


def _signature_details(tag: Tag) -> dict[str, Any]:
    field_type = str(tag.get("data-field-type") or "signature")
    defaults = {
        "signature": "Signature",
        "initials": "Initials",
        "date": "Date signed",
        "name": "Full name",
        "title": "Title / capacity",
        "text": "Text field",
        "checkbox": "Checkbox",
    }
    return {
        "field_id": str(tag.get("data-field-id") or ""),
        "field_type": field_type,
        "label": str(tag.get("data-label") or defaults.get(field_type, "Signature field")),
        "assigned_to": str(tag.get("data-assigned-to") or "Signer"),
        "required": str(tag.get("data-required") or "false").lower() == "true",
        "placeholder": str(tag.get("data-placeholder") or "Sign or complete here"),
        "width": min(100, max(25, int(float(tag.get("data-width") or 100)))),
        "height": min(120, max(28, int(float(tag.get("data-height") or 56)))),
    }


def _signature_timestamp(value: datetime | None) -> str:
    return value.strftime("%d %B %Y %H:%M") if value else ""


def _pdf_signature_field(
    tag: Tag,
    theme: DocumentTheme,
    signature: WorkspaceDocumentSignature | None = None,
) -> Table:
    info = _signature_details(tag)
    required = " · REQUIRED" if info["required"] else ""
    label = Paragraph(
        f'<b>{html.escape(info["label"])}</b><br/><font size="7" color="#64748B">{html.escape(info["assigned_to"])}{required}</font>',
        ParagraphStyle("SignatureLabel", fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=colors.HexColor(theme.heading)),
    )

    value: Any
    if signature is not None:
        meta = (
            f'<br/><font size="6.8" color="#64748B">Signed by {html.escape(signature.signer_name)} · '
            f'{html.escape(_signature_timestamp(signature.signed_at))}<br/>Verification: {html.escape(signature.verification_code)}</font>'
        )
        if signature.method == "stored_signature" and signature.asset:
            try:
                image = Image(BytesIO(asset_image_bytes(signature.asset)), width=48 * mm, height=18 * mm, kind="proportional")
                meta_para = Paragraph(meta.lstrip("<br/>"), ParagraphStyle("SignatureSignedMeta", fontName="Helvetica", fontSize=7, leading=9))
                value = Table([[image], [meta_para]], colWidths=[99 * mm])
                value.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
            except Exception:
                value = Paragraph(f'<b>{html.escape(signature.signer_name)}</b>{meta}', ParagraphStyle("SignatureElectronic", fontName="Helvetica-Oblique", fontSize=12, leading=15, textColor=colors.HexColor(theme.heading)))
        else:
            value = Paragraph(
                f'<font name="Helvetica-Oblique" size="13">{html.escape(signature.signer_name)}</font>{meta}',
                ParagraphStyle("SignatureElectronic", fontName="Helvetica", fontSize=10, leading=13, textColor=colors.HexColor(theme.heading)),
            )
    elif info["field_type"] == "checkbox":
        value = Paragraph("[ ] &nbsp; " + html.escape(info["placeholder"]), ParagraphStyle("SignatureValueCheck", fontName="Helvetica", fontSize=10, leading=13))
    else:
        line_count = max(1, min(4, info["height"] // 25))
        lines = "<br/>".join("________________________________________" for _ in range(line_count))
        value = Paragraph(lines, ParagraphStyle("SignatureValue", fontName="Helvetica", fontSize=9, leading=14, textColor=colors.HexColor("#475569")))

    table = Table([[label, value]], colWidths=[48 * mm, 105 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(theme.soft)),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(theme.accent)),
        ("LINEBEFORE", (0, 0), (0, -1), 3.0, colors.HexColor(theme.accent)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table

def _pdf_paragraph(tag: Tag, style: ParagraphStyle, document: WorkspaceDocument, theme: DocumentTheme) -> Paragraph:
    font_size = _font_size_pt(_style_value(tag, "font-size"), style.fontSize or _document_font_size(document))
    line_height_value = _style_value(tag, "line-height")
    if line_height_value and line_height_value.endswith("%"):
        leading = font_size * _css_number(line_height_value, default=_document_line_height(document)) / 100
    elif line_height_value:
        numeric = _css_number(line_height_value, default=1.15)
        leading = font_size * numeric if numeric <= 4 else numeric
    else:
        leading = font_size * _document_line_height(document) / 100
    family = _style_value(tag, "font-family") or _document_font_family(document)
    background = _style_value(tag, "background-color")
    current = ParagraphStyle(
        f"Dynamic-{uuid.uuid4().hex}",
        parent=style,
        alignment=_alignment(tag),
        fontName=_pdf_font_name(family),
        fontSize=font_size,
        leading=max(font_size + 1, leading),
        textColor=colors.HexColor(_style_value(tag, "color") or theme.body),
        backColor=colors.HexColor(background) if background and re.fullmatch(r"#[0-9a-fA-F]{6}", background) else None,
        leftIndent=_css_number(_style_value(tag, "margin-left")) * mm,
        rightIndent=_css_number(_style_value(tag, "margin-right")) * mm,
        firstLineIndent=_css_number(_style_value(tag, "text-indent")) * mm,
        spaceBefore=_css_number(_style_value(tag, "margin-top")) * 0.75,
        spaceAfter=max(2, _css_number(_style_value(tag, "margin-bottom"), default=4) * 0.75),
    )
    return Paragraph("".join(_reportlab_inline(child) for child in tag.children) or "&nbsp;", current)


def _pdf_story_from_html(document: WorkspaceDocument, signatures: dict[str, WorkspaceDocumentSignature] | None = None) -> list[Any]:
    soup = BeautifulSoup(strip_legacy_filizwa_placeholder_header(document.content_html), "html.parser")
    theme = _theme(document)
    signatures = signatures or {}
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "LetterBody",
        parent=base["BodyText"],
        fontName=_pdf_font_name(_document_font_family(document)),
        fontSize=_document_font_size(document),
        leading=_document_font_size(document) * _document_line_height(document) / 100,
        textColor=colors.HexColor(theme.body),
        spaceAfter=3 * mm,
    )
    heading1 = ParagraphStyle("LetterH1", parent=base["Heading1"], fontName=_pdf_font_name(_document_font_family(document), bold=True), fontSize=20, leading=24, textColor=colors.HexColor(theme.heading), spaceBefore=3 * mm, spaceAfter=3 * mm)
    heading2 = ParagraphStyle("LetterH2", parent=base["Heading2"], fontName=_pdf_font_name(_document_font_family(document), bold=True), fontSize=14, leading=18, textColor=colors.HexColor(theme.heading), spaceBefore=3 * mm, spaceAfter=2 * mm)
    heading3 = ParagraphStyle("LetterH3", parent=base["Heading3"], fontName=_pdf_font_name(_document_font_family(document), bold=True), fontSize=11.5, leading=15, textColor=colors.HexColor(theme.heading), spaceBefore=2.5 * mm, spaceAfter=1.5 * mm)
    quote = ParagraphStyle("LetterQuote", parent=body, leftIndent=8 * mm, borderColor=colors.HexColor(theme.accent), borderWidth=1, borderPadding=5, backColor=colors.HexColor(theme.soft), textColor=colors.HexColor(theme.body))
    story: list[Any] = []

    def append_node(node: Tag) -> None:
        if node.get("data-page-break") is not None or _style_value(node, "page-break-after") == "always":
            story.append(PageBreak())
            return
        if node.get("data-signature-field") is not None:
            field_id = str(node.get("data-field-id") or "")
            story.extend([_pdf_signature_field(node, theme, signatures.get(field_id)), Spacer(1, 3 * mm)])
            return
        if node.name in {"h1", "h2", "h3", "h4"}:
            styles = {"h1": heading1, "h2": heading2, "h3": heading3, "h4": heading3}
            story.append(_pdf_paragraph(node, styles[node.name], document, theme))
        elif node.name in {"p", "div", "pre"}:
            story.append(_pdf_paragraph(node, body, document, theme))
        elif node.name == "blockquote":
            story.append(_pdf_paragraph(node, quote, document, theme))
        elif node.name in {"ul", "ol"}:
            items = []
            for item in node.find_all("li", recursive=False):
                items.append(ListItem(_pdf_paragraph(item, body, document, theme), leftIndent=5 * mm))
            if items:
                story.append(ListFlowable(items, bulletType="1" if node.name == "ol" else "bullet", leftIndent=8 * mm, bulletFontSize=8))
                story.append(Spacer(1, 2 * mm))
        elif node.name == "table":
            rows: list[list[Any]] = []
            for tr in node.find_all("tr"):
                cells = tr.find_all(["th", "td"], recursive=False)
                if cells:
                    rows.append([_pdf_paragraph(cell, body, document, theme) for cell in cells])
            if rows:
                max_cols = max(len(row) for row in rows)
                for row in rows:
                    row.extend([""] * (max_cols - len(row)))
                table = Table(rows, repeatRows=1 if node.find("th") else 0, hAlign="LEFT")
                style_commands = [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
                if node.find("th"):
                    style_commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(theme.soft)))
                table.setStyle(TableStyle(style_commands))
                story.extend([table, Spacer(1, 3 * mm)])
        elif node.name == "img":
            payload = _data_image(str(node.get("src") or ""))
            if payload:
                try:
                    reader = ImageReader(BytesIO(payload))
                    width, height = reader.getSize()
                    scale = min((155 * mm) / width, (95 * mm) / height, 1)
                    story.extend([Image(BytesIO(payload), width=width * scale, height=height * scale), Spacer(1, 3 * mm)])
                except Exception:
                    pass
        elif node.name == "hr":
            story.extend([HRFlowable(width="100%", thickness=0.8, color=colors.HexColor(theme.accent)), Spacer(1, 3 * mm)])

    for child in soup.contents:
        if isinstance(child, Tag):
            append_node(child)
    return story or [Paragraph("", body)]


def _workspace_page_size(document: WorkspaceDocument):
    size = LETTER if getattr(document, "page_size", "A4") == "LETTER" else A4
    return landscape(size) if getattr(document, "orientation", "portrait") == "landscape" else size


def _draw_fitted_canvas_image(canvas, payload: bytes, x: float, y: float, max_w: float, max_h: float, *, align: str = "left") -> None:
    try:
        reader = ImageReader(BytesIO(payload))
        source_w, source_h = reader.getSize()
        scale = min(max_w / float(source_w), max_h / float(source_h))
        draw_w = source_w * scale
        draw_h = source_h * scale
        draw_x = x if align == "left" else x + max_w - draw_w if align == "right" else x + (max_w - draw_w) / 2
        draw_y = y + (max_h - draw_h) / 2
        canvas.drawImage(reader, draw_x, draw_y, width=draw_w, height=draw_h, mask="auto")
    except Exception:
        return


def _cover_story(document: WorkspaceDocument, brand_asset: WorkspaceDocumentAsset | None) -> list[Any]:
    if not getattr(document, "cover_page_enabled", False):
        return []
    cover = dict(getattr(document, "cover_page", None) or {})
    theme = _theme(document)
    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=base["Title"],
        fontName=_pdf_font_name(_document_font_family(document), bold=True),
        fontSize=30,
        leading=35,
        textColor=colors.HexColor(theme.heading),
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
    )
    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=base["BodyText"],
        fontName=_pdf_font_name(_document_font_family(document)),
        fontSize=13,
        leading=18,
        textColor=colors.HexColor(theme.body),
        alignment=TA_CENTER,
        spaceAfter=12 * mm,
    )
    detail_style = ParagraphStyle(
        "CoverDetail",
        parent=base["BodyText"],
        fontName=_pdf_font_name(_document_font_family(document)),
        fontSize=10,
        leading=15,
        textColor=colors.HexColor(theme.body),
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
    )
    story: list[Any] = [Spacer(1, 34 * mm)]
    if cover.get("show_logo", True) and brand_asset:
        try:
            reader = ImageReader(BytesIO(asset_image_bytes(brand_asset)))
            w, h = reader.getSize()
            scale = min((70 * mm) / w, (30 * mm) / h)
            story.extend([Image(BytesIO(asset_image_bytes(brand_asset)), width=w * scale, height=h * scale), Spacer(1, 12 * mm)])
            story[-2].hAlign = "CENTER"
        except Exception:
            pass
    story.extend([
        Paragraph(html.escape(str(cover.get("title") or document.title)), title_style),
        Paragraph(html.escape(str(cover.get("subtitle") or "")) or "&nbsp;", subtitle_style),
        HRFlowable(width="45%", thickness=2, color=colors.HexColor(theme.accent), hAlign="CENTER"),
        Spacer(1, 10 * mm),
    ])
    details = [
        ("Prepared for", cover.get("prepared_for")),
        ("Prepared by", cover.get("prepared_by") or user_display_name(document.owner)),
        ("Date", cover.get("document_date")),
        ("Version", cover.get("version_label") or f"Version {document.version}"),
    ]
    for label, value in details:
        if value:
            story.append(Paragraph(f'<b>{html.escape(label)}:</b> {html.escape(str(value))}', detail_style))
    if cover.get("show_reference", True):
        story.append(Paragraph(f'<b>Reference:</b> {html.escape(document.reference)}', detail_style))
    if cover.get("confidentiality_note"):
        story.extend([Spacer(1, 12 * mm), Paragraph(html.escape(str(cover["confidentiality_note"])), detail_style)])
    story.append(PageBreak())
    return story


def _draw_address_blocks(
    canvas,
    document: WorkspaceDocument,
    page_width: float,
    page_height: float,
    *,
    first_body_page: bool,
) -> None:
    theme = _theme(document)
    for block in list(getattr(document, "address_blocks", None) or []):
        if block.get("first_page_only", True) and not first_body_page:
            continue
        try:
            x = float(block.get("x_mm", 22)) * mm
            y_top = page_height - float(block.get("y_mm", 48)) * mm
            width = max(25.0, float(block.get("width_mm", 70))) * mm
            size = max(7, min(18, int(block.get("font_size_pt", 9))))
            alignment = {"center": TA_CENTER, "right": TA_RIGHT}.get(str(block.get("alignment", "left")), TA_LEFT)
            pieces = []
            if block.get("show_label", True) and str(block.get("label") or "").strip():
                pieces.append(f'<b>{html.escape(str(block.get("label")))}</b>')
            content = html.escape(str(block.get("content") or "")).replace("\n", "<br/>")
            if content:
                pieces.append(content)
            if not pieces:
                continue
            paragraph = Paragraph(
                "<br/>".join(pieces),
                ParagraphStyle(
                    f"Address-{block.get('id', uuid.uuid4().hex)}",
                    fontName=_pdf_font_name(_document_font_family(document)),
                    fontSize=size,
                    leading=size * 1.25,
                    textColor=colors.HexColor(theme.body),
                    alignment=alignment,
                ),
            )
            _, height = paragraph.wrap(width, 80 * mm)
            paragraph.drawOn(canvas, x, y_top - height)
        except Exception:
            continue


def _company_header_lines(company: LoanCompany | None) -> list[str]:
    if company is None:
        return [settings.PRODUCT_NAME]
    lines = [company.name]
    legal_parts = []
    if company.registration_number:
        legal_parts.append(f"Registration: {company.registration_number}")
    if company.license_number:
        legal_parts.append(f"Licence: {company.license_number}")
    if legal_parts:
        lines.append(" · ".join(legal_parts))
    contact_parts = [part for part in [company.phone, company.email, company.website] if part]
    if contact_parts:
        lines.append(" · ".join(contact_parts))
    address_parts = [part for part in [company.address, company.district] if part]
    if address_parts:
        lines.append(" · ".join(address_parts))
    return lines


def _header_right_logo_bytes(
    db: Session,
    document: WorkspaceDocument,
    company: LoanCompany | None,
    brand_asset: WorkspaceDocumentAsset | None,
) -> bytes | None:
    # A logo chosen for this document is explicit and takes precedence.
    if document.brand_logo_asset_id and brand_asset:
        return asset_image_bytes(brand_asset)
    logos = get_company_branding_logos(db, company)
    if logos.right_logo:
        return logos.right_logo
    if brand_asset:
        return asset_image_bytes(brand_asset)
    return None


def _draw_workspace_page(
    canvas,
    doc,
    *,
    db: Session,
    document: WorkspaceDocument,
    company: LoanCompany | None,
    brand_asset: WorkspaceDocumentAsset | None,
) -> None:
    page_width, page_height = _workspace_page_size(document)
    is_cover = bool(getattr(document, "cover_page_enabled", False) and doc.page == 1)
    first_body_page = 2 if getattr(document, "cover_page_enabled", False) else 1
    theme = _theme(document)
    canvas.saveState()

    if not is_cover and getattr(document, "include_brand_header", True):
        logos = get_company_branding_logos(db, company)
        top_y = page_height - 23 * mm
        if logos.left_logo:
            _draw_fitted_canvas_image(canvas, logos.left_logo, 18 * mm, top_y, 38 * mm, 12 * mm, align="left")
        else:
            canvas.setFillColor(colors.HexColor(theme.heading))
            canvas.setFont("Helvetica-Bold", 13)
            canvas.drawString(18 * mm, page_height - 16 * mm, settings.PRODUCT_NAME)

        right_logo = _header_right_logo_bytes(db, document, company, brand_asset)
        if right_logo:
            _draw_fitted_canvas_image(canvas, right_logo, page_width - 62 * mm, top_y, 44 * mm, 12 * mm, align="right")

        # Keep the legal/company identity visually centred between the two logos.
        header_lines = _company_header_lines(company)
        center_x = page_width / 2
        line_y = page_height - 13 * mm
        for index, line in enumerate(header_lines[:4]):
            canvas.setFillColor(colors.HexColor(theme.heading if index == 0 else "#64748B"))
            canvas.setFont("Helvetica-Bold" if index == 0 else "Helvetica", 8.8 if index == 0 else 6.4)
            canvas.drawCentredString(center_x, line_y - index * 4 * mm, line[:92])

        canvas.setStrokeColor(colors.HexColor(theme.accent))
        canvas.setLineWidth(1.1)
        canvas.line(18 * mm, page_height - 29 * mm, page_width - 18 * mm, page_height - 29 * mm)

    if not is_cover and getattr(document, "include_footer", True):
        canvas.setStrokeColor(colors.HexColor("#D4DEE8"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 14 * mm, page_width - 18 * mm, 14 * mm)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.setFont("Helvetica", 6.6)
        prefix = "CONFIDENTIAL · " if getattr(document, "is_confidential", False) else ""
        canvas.drawString(18 * mm, 9.5 * mm, f"{prefix}{document.reference}"[:72])
        canvas.drawCentredString(page_width / 2, 9.5 * mm, f"{settings.PRODUCT_NAME} Document Studio")
        canvas.drawRightString(page_width - 18 * mm, 9.5 * mm, f"Page {doc.page}")

    if not is_cover:
        _draw_address_blocks(
            canvas,
            document,
            page_width,
            page_height,
            first_body_page=doc.page == first_body_page,
        )
    canvas.restoreState()


def export_pdf(db: Session, document: WorkspaceDocument, company: LoanCompany | None) -> bytes:
    page_size = _workspace_page_size(document)
    buffer = BytesIO()
    document_pdf = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=getattr(document, "margin_right_mm", 22) * mm,
        leftMargin=getattr(document, "margin_left_mm", 22) * mm,
        topMargin=max(34, getattr(document, "margin_top_mm", 28)) * mm,
        bottomMargin=max(19, getattr(document, "margin_bottom_mm", 24)) * mm,
        title=document.title,
        author=user_display_name(document.owner),
        subject="LoanHub workspace document",
        creator=f"{settings.PRODUCT_NAME} by {settings.DEVELOPER_NAME}",
    )
    brand_asset = resolved_brand_asset(db, document)
    document_id = getattr(document, "id", None)
    signatures = active_signatures(db, document_id) if document_id is not None else {}
    story = _cover_story(document, brand_asset) + _pdf_story_from_html(document, signatures)

    def draw(canvas, doc):
        _draw_workspace_page(
            canvas,
            doc,
            db=db,
            document=document,
            company=company,
            brand_asset=brand_asset,
        )

    document_pdf.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()

def _set_cell_text(cell, text: str, *, bold: bool = False, size: float = 9) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)


def _shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill.lstrip("#"))


def _set_cell_border(cell, *, color: str = "CBD5E1", size: str = "6") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), size)
        node.set(qn("w:color"), color.lstrip("#"))


def _add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.add_run("Page ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)


def _word_header(
    word: WordDocument,
    db: Session,
    company: LoanCompany | None,
    document: WorkspaceDocument,
    brand_asset: WorkspaceDocumentAsset | None,
) -> None:
    section = word.sections[0]
    header = section.header
    available_width = section.page_width - section.left_margin - section.right_margin
    table = header.add_table(rows=1, cols=3, width=available_width)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.columns[0].width = available_width * 0.24
    table.columns[1].width = available_width * 0.52
    table.columns[2].width = available_width * 0.24
    logos = get_company_branding_logos(db, company)
    if logos.left_logo:
        table.cell(0, 0).paragraphs[0].add_run().add_picture(BytesIO(logos.left_logo), width=Mm(31))
    else:
        _set_cell_text(table.cell(0, 0), settings.PRODUCT_NAME, bold=True, size=11)

    center = table.cell(0, 1).paragraphs[0]
    center.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for index, line in enumerate(_company_header_lines(company)):
        if index:
            center.add_run("\n")
        run = center.add_run(line)
        run.bold = index == 0
        run.font.size = Pt(9 if index == 0 else 6.8)

    right = table.cell(0, 2).paragraphs[0]
    right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    right_logo = _header_right_logo_bytes(db, document, company, brand_asset)
    if right_logo:
        right.add_run().add_picture(BytesIO(right_logo), width=Mm(34))

    for cell in table.rows[0].cells:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    border_paragraph = header.add_paragraph()
    p_pr = border_paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:color"), _theme(document).accent.lstrip("#"))
    borders.append(bottom)
    p_pr.append(borders)

def _word_font(run, family: str | None) -> None:
    if not family:
        return
    run.font.name = family
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        r_fonts.set(qn(f"w:{key}"), family)


def _word_add_inline(paragraph, node: Tag | NavigableString, inherited: dict[str, Any] | None = None) -> None:
    inherited = dict(inherited or {})
    if isinstance(node, NavigableString):
        if str(node):
            run = paragraph.add_run(str(node))
            run.bold = inherited.get("bold", False)
            run.italic = inherited.get("italic", False)
            run.underline = inherited.get("underline", False)
            run.font.strike = inherited.get("strike", False)
            run.font.subscript = inherited.get("subscript", False)
            run.font.superscript = inherited.get("superscript", False)
            _word_font(run, inherited.get("font_family"))
            if inherited.get("size"):
                run.font.size = Pt(inherited["size"])
            if inherited.get("color"):
                try:
                    run.font.color.rgb = RGBColor.from_string(inherited["color"].lstrip("#"))
                except Exception:
                    pass
        return
    name = node.name.lower()
    if name in {"strong", "b"}:
        inherited["bold"] = True
    if name in {"em", "i"}:
        inherited["italic"] = True
    if name == "u":
        inherited["underline"] = True
    if name in {"s", "strike"}:
        inherited["strike"] = True
    if name == "sub":
        inherited["subscript"] = True
    if name == "sup":
        inherited["superscript"] = True
    family = _style_value(node, "font-family")
    if family:
        inherited["font_family"] = family.split(",")[0].strip(" '\"")
    color = _style_value(node, "color")
    if color and re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        inherited["color"] = color
    size = _style_value(node, "font-size")
    if size:
        inherited["size"] = _font_size_pt(size, 11)
    if name == "br":
        paragraph.add_run().add_break()
        return
    for child in node.children:
        _word_add_inline(paragraph, child, inherited)


def _word_alignment(tag: Tag) -> WD_ALIGN_PARAGRAPH:
    value = (_style_value(tag, "text-align") or "left").lower()
    return {
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }.get(value, WD_ALIGN_PARAGRAPH.LEFT)


def _word_paragraph(container, tag: Tag, document: WorkspaceDocument, style: str | None = None):
    paragraph = container.add_paragraph(style=style)
    paragraph.alignment = _word_alignment(tag)
    paragraph.paragraph_format.line_spacing = max(0.8, _document_line_height(document) / 100)
    margin_top = _css_number(_style_value(tag, "margin-top"))
    margin_bottom = _css_number(_style_value(tag, "margin-bottom"), default=6)
    paragraph.paragraph_format.space_before = Pt(margin_top * 0.75)
    paragraph.paragraph_format.space_after = Pt(margin_bottom * 0.75)
    paragraph.paragraph_format.left_indent = Mm(_css_number(_style_value(tag, "margin-left")))
    paragraph.paragraph_format.right_indent = Mm(_css_number(_style_value(tag, "margin-right")))
    paragraph.paragraph_format.first_line_indent = Mm(_css_number(_style_value(tag, "text-indent")))
    _word_add_inline(paragraph, tag, {
        "font_family": _style_value(tag, "font-family") or _document_font_family(document),
        "size": _font_size_pt(_style_value(tag, "font-size"), _document_font_size(document)),
    })
    return paragraph


def _word_signature_field(
    word: WordDocument,
    tag: Tag,
    document: WorkspaceDocument,
    signature: WorkspaceDocumentSignature | None = None,
) -> None:
    theme = _theme(document)
    info = _signature_details(tag)
    table = word.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Mm(48)
    table.columns[1].width = Mm(105)
    label_cell, value_cell = table.rows[0].cells
    _shade_cell(label_cell, theme.soft)
    for cell in (label_cell, value_cell):
        _set_cell_border(cell, color=theme.accent, size="8")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _set_cell_text(label_cell, info["label"], bold=True, size=9)
    meta = label_cell.add_paragraph(f'{info["assigned_to"]}{" · REQUIRED" if info["required"] else ""}')
    meta.runs[0].font.size = Pt(7)
    meta.runs[0].font.color.rgb = RGBColor(100, 116, 139)

    if signature is not None:
        value_cell.text = ""
        paragraph = value_cell.paragraphs[0]
        if signature.method == "stored_signature" and signature.asset:
            try:
                paragraph.add_run().add_picture(BytesIO(asset_image_bytes(signature.asset)), width=Mm(52))
            except Exception:
                run = paragraph.add_run(signature.signer_name)
                run.italic = True
                run.font.size = Pt(13)
        else:
            run = paragraph.add_run(signature.signer_name)
            run.italic = True
            run.font.size = Pt(13)
        details = value_cell.add_paragraph(
            f"Signed {_signature_timestamp(signature.signed_at)}\nVerification: {signature.verification_code}"
        )
        details.runs[0].font.size = Pt(7)
        details.runs[0].font.color.rgb = RGBColor(100, 116, 139)
    elif info["field_type"] == "checkbox":
        _set_cell_text(value_cell, f'☐  {info["placeholder"]}', size=10)
    else:
        _set_cell_text(value_cell, "\n".join("________________________________" for _ in range(max(1, min(4, info["height"] // 25)))), size=9)
    word.add_paragraph().paragraph_format.space_after = Pt(0)

def _word_content(word: WordDocument, document: WorkspaceDocument, signatures: dict[str, WorkspaceDocumentSignature] | None = None) -> None:
    soup = BeautifulSoup(strip_legacy_filizwa_placeholder_header(document.content_html), "html.parser")
    signatures = signatures or {}
    for node in soup.contents:
        if not isinstance(node, Tag):
            continue
        if node.get("data-page-break") is not None or _style_value(node, "page-break-after") == "always":
            word.add_page_break()
        elif node.get("data-signature-field") is not None:
            field_id = str(node.get("data-field-id") or "")
            _word_signature_field(word, node, document, signatures.get(field_id))
        elif node.name in {"h1", "h2", "h3", "h4"}:
            _word_paragraph(word, node, document, f"Heading {min(int(node.name[1]), 3)}")
        elif node.name in {"p", "div", "blockquote", "pre"}:
            paragraph = _word_paragraph(word, node, document)
            if node.name == "blockquote":
                paragraph.paragraph_format.left_indent = Mm(8)
        elif node.name in {"ul", "ol"}:
            style = "List Number" if node.name == "ol" else "List Bullet"
            for item in node.find_all("li", recursive=False):
                _word_paragraph(word, item, document, style)
        elif node.name == "table":
            source_rows = node.find_all("tr")
            width = max((len(row.find_all(["td", "th"], recursive=False)) for row in source_rows), default=1)
            table = word.add_table(rows=0, cols=width)
            table.style = "Table Grid"
            for source_row in source_rows:
                target = table.add_row().cells
                cells = source_row.find_all(["td", "th"], recursive=False)
                for index, cell in enumerate(cells):
                    target[index].text = ""
                    if cell.name == "th":
                        _shade_cell(target[index], _theme(document).soft)
                    _word_add_inline(target[index].paragraphs[0], cell, {
                        "bold": cell.name == "th",
                        "font_family": _document_font_family(document),
                        "size": _document_font_size(document) - 1,
                    })
        elif node.name == "img":
            payload = _data_image(str(node.get("src") or ""))
            if payload:
                try:
                    word.add_picture(BytesIO(payload), width=Mm(150))
                except Exception:
                    pass
        elif node.name == "hr":
            paragraph = word.add_paragraph()
            p_pr = paragraph._p.get_or_add_pPr()
            borders = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "8")
            bottom.set(qn("w:color"), _theme(document).accent.lstrip("#"))
            borders.append(bottom)
            p_pr.append(borders)


def _configure_word_styles(word: WordDocument, document: WorkspaceDocument) -> None:
    theme = _theme(document)
    normal = word.styles["Normal"]
    normal.font.name = _document_font_family(document)
    normal.font.size = Pt(_document_font_size(document))
    normal.font.color.rgb = RGBColor.from_string(theme.body.lstrip("#"))
    normal.paragraph_format.line_spacing = _document_line_height(document) / 100
    normal.paragraph_format.space_after = Pt(6)
    for index, size in ((1, 20), (2, 14), (3, 11.5)):
        style = word.styles[f"Heading {index}"]
        style.font.name = _document_font_family(document)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(theme.heading.lstrip("#"))


def _word_cover_page(word: WordDocument, document: WorkspaceDocument, brand_asset: WorkspaceDocumentAsset | None) -> None:
    if not getattr(document, "cover_page_enabled", False):
        return
    cover = dict(getattr(document, "cover_page", None) or {})
    if cover.get("show_logo", True) and brand_asset:
        paragraph = word.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        try:
            paragraph.add_run().add_picture(BytesIO(asset_image_bytes(brand_asset)), width=Mm(62))
        except Exception:
            pass
    word.add_paragraph().paragraph_format.space_after = Pt(24)
    title = word.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(str(cover.get("title") or document.title))
    run.bold = True
    run.font.size = Pt(30)
    _word_font(run, _document_font_family(document))
    if cover.get("subtitle"):
        subtitle = word.add_paragraph(str(cover.get("subtitle")))
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle.runs[0].font.size = Pt(14)
    word.add_paragraph().paragraph_format.space_after = Pt(18)
    details = [
        ("Prepared for", cover.get("prepared_for")),
        ("Prepared by", cover.get("prepared_by") or user_display_name(document.owner)),
        ("Date", cover.get("document_date")),
        ("Version", cover.get("version_label") or f"Version {document.version}"),
    ]
    for label, value in details:
        if value:
            paragraph = word.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            label_run = paragraph.add_run(f"{label}: ")
            label_run.bold = True
            paragraph.add_run(str(value))
    if cover.get("show_reference", True):
        paragraph = word.add_paragraph(f"Reference: {document.reference}")
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if cover.get("confidentiality_note"):
        word.add_paragraph().paragraph_format.space_after = Pt(18)
        paragraph = word.add_paragraph(str(cover.get("confidentiality_note")))
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.runs[0].italic = True
    word.add_page_break()


def _word_address_blocks(word: WordDocument, document: WorkspaceDocument) -> None:
    """Create floating Word frames at writer-defined page coordinates."""
    twips_per_mm = 56.6929133858
    for block in list(getattr(document, "address_blocks", None) or []):
        content = str(block.get("content") or "").strip()
        label = str(block.get("label") or "").strip()
        if not content and not label:
            continue
        paragraph = word.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.alignment = {
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
        }.get(str(block.get("alignment", "left")), WD_ALIGN_PARAGRAPH.LEFT)
        if block.get("show_label", True) and label:
            run = paragraph.add_run(label + "\n")
            run.bold = True
            run.font.size = Pt(max(7, min(18, int(block.get("font_size_pt", 9)))))
        if content:
            run = paragraph.add_run(content)
            run.font.size = Pt(max(7, min(18, int(block.get("font_size_pt", 9)))))
        p_pr = paragraph._p.get_or_add_pPr()
        frame = OxmlElement("w:framePr")
        frame.set(qn("w:w"), str(int(float(block.get("width_mm", 70)) * twips_per_mm)))
        frame.set(qn("w:x"), str(int(float(block.get("x_mm", 22)) * twips_per_mm)))
        frame.set(qn("w:y"), str(int(float(block.get("y_mm", 48)) * twips_per_mm)))
        frame.set(qn("w:hAnchor"), "page")
        frame.set(qn("w:vAnchor"), "page")
        frame.set(qn("w:wrap"), "around")
        frame.set(qn("w:anchorLock"), "1")
        p_pr.append(frame)


def export_docx(db: Session, document: WorkspaceDocument, company: LoanCompany | None) -> bytes:
    word = WordDocument()
    section = word.sections[0]
    if getattr(document, "page_size", "A4") == "LETTER":
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
    else:
        section.page_width = Mm(210)
        section.page_height = Mm(297)
    if getattr(document, "orientation", "portrait") == "landscape":
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Mm(max(34, getattr(document, "margin_top_mm", 28)))
    section.right_margin = Mm(getattr(document, "margin_right_mm", 22))
    section.bottom_margin = Mm(getattr(document, "margin_bottom_mm", 24))
    section.left_margin = Mm(getattr(document, "margin_left_mm", 22))

    _configure_word_styles(word, document)
    brand_asset = resolved_brand_asset(db, document)
    document_id = getattr(document, "id", None)
    signatures = active_signatures(db, document_id) if document_id is not None else {}

    if getattr(document, "cover_page_enabled", False):
        section.different_first_page_header_footer = True
    if getattr(document, "include_brand_header", True):
        _word_header(word, db, company, document, brand_asset)
    if getattr(document, "include_footer", True):
        footer = section.footer.paragraphs[0]
        footer.add_run(f'{"CONFIDENTIAL | " if getattr(document, "is_confidential", False) else ""}{document.reference} | Version {document.version} | ')
        _add_page_number(footer)

    core = word.core_properties
    core.title = document.title
    core.author = user_display_name(document.owner)
    core.subject = "LoanHub workspace document"
    core.comments = f"Generated by {settings.PRODUCT_NAME}"

    _word_cover_page(word, document, brand_asset)
    _word_address_blocks(word, document)
    _word_content(word, document, signatures)
    buffer = BytesIO()
    word.save(buffer)
    return buffer.getvalue()

