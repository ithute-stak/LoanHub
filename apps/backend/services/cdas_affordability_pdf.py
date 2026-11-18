"""Confidential LoanHub government employee affordability assessment PDF.

Renders *stored server-side snapshots only*. No CDAS calls or underwriting recalculation.
"""
from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.document_branding_service import draw_brand_header, draw_brand_footer


def build_government_affordability_pdf(*, db, company, snapshot: dict) -> bytes:
    """Render an immutable assessment snapshot supplied by trusted storage.

    Required snapshot keys must have been persisted after live verification:
    reference, employee_number, borrower_id, assessed_at, cdas_capacity,
    proposed_installment, maximum_affordable_installment, decision, policy_version.
    """
    required = (
        "reference", "employee_number", "borrower_id", "assessed_at",
        "cdas_capacity", "proposed_installment", "maximum_affordable_installment",
        "decision", "policy_version",
    )
    missing = [key for key in required if snapshot.get(key) is None]
    if missing:
        raise ValueError("Incomplete stored affordability assessment: " + ", ".join(missing))

    buffer = BytesIO()
    width, height = A4
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=52 * mm, bottomMargin=25 * mm,
        title="LoanHub Government Employee Affordability Assessment",
        author="LoanHub",
    )
    heading = ParagraphStyle("assessmentTitle", fontName="Helvetica-Bold", fontSize=13,
                             leading=17, textColor=colors.HexColor("#0F2742"), spaceAfter=10)
    section = ParagraphStyle("assessmentSection", fontName="Helvetica-Bold", fontSize=10,
                             leading=13, textColor=colors.HexColor("#0F2742"), spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("assessmentBody", fontName="Helvetica", fontSize=8.5,
                          leading=13, textColor=colors.HexColor("#172033"))
    note = ParagraphStyle("assessmentNote", parent=body, fontSize=8, leading=12)
    def cell(value):
        return Paragraph(escape(str(value if value is not None else "Not available")), body)

    story = [
        Paragraph("GOVERNMENT EMPLOYEE AFFORDABILITY ASSESSMENT", heading),
        Paragraph("CONFIDENTIAL — Loan assessment support only. Not approval or payroll deduction authorisation.", note),
        Spacer(1, 7 * mm),
    ]
    sections = [
        ("Assessment identity", [
            ("Report reference", snapshot["reference"]),
            ("Assessment timestamp", snapshot["assessed_at"]),
            ("Borrower record ID", snapshot["borrower_id"]),
            ("Employee number", snapshot["employee_number"]),
            ("Identity verification", snapshot.get("identity_status", "Verified during assessment")),
            ("Department / Ministry", snapshot.get("department")),
        ]),
        ("Affordability (Lesotho maloti)", [
            ("CDAS reported monthly capacity", snapshot["cdas_capacity"]),
            ("LoanHub policy maximum instalment", snapshot["maximum_affordable_installment"]),
            ("Proposed monthly instalment", snapshot["proposed_installment"]),
            ("Assessment decision", snapshot["decision"]),
            ("Internal policy version", snapshot["policy_version"]),
            ("CDAS environment", snapshot.get("cdas_environment", "Unknown")),
        ]),
    ]
    for label, entries in sections:
        story.append(Paragraph(label, section))
        rows = [[cell(k), cell(v)] for k, v in entries]
        table = Table(rows, colWidths=[74 * mm, 100 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F4F7FB")]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#D4DEE8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "Source note: CDAS capacity is a provider-reported amount captured at assessment time. "
        "The maximum instalment and decision are LoanHub policy calculations. "
        "Capacity may change; this document is not a commitment to lend.", note,
    ))
    story.append(Paragraph(
        "Document integrity: generated from an archived assessment snapshot. "
        "Downloading this report must not trigger a new CDAS request, approval, or deduction.", note,
    ))

    reference = str(snapshot["reference"])
    def decorate(canvas, template):
        draw_brand_header(
            canvas, db=db, company=company,
            title="AFFORDABILITY ASSESSMENT",
            subtitle="Government employee | Confidential",
            width=width, height=height,
        )
        draw_brand_footer(
            canvas, template, reference_text=reference[:65],
            note_text="LoanHub Document Studio | Confidential", width=width,
        )
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()
