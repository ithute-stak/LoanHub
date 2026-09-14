from __future__ import annotations

from datetime import date, datetime, timezone
from html import escape
from typing import Any
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from database.models.company import LoanCompany
from services.pdf_design_system import (
    BORDER,
    CONTENT_WIDTH,
    DocumentContext,
    build_document,
    callout,
    detail_card,
    document_styles,
    generated_timestamp,
    hero_block,
    humanize,
    metric_grid,
    money_text,
    section,
    two_card_row,
)


def _text(value: Any, fallback: str = "Not recorded") -> str:
    raw = str(value or "").strip()
    return escape(raw or fallback)


def _date_text(value: Any, fallback: str = "Not recorded") -> str:
    if not value:
        return fallback
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d %B %Y")
    try:
        parsed = date.fromisoformat(str(value)[:10])
        return parsed.strftime("%d %B %Y")
    except (TypeError, ValueError):
        return _text(value, fallback)


def _decision_tone(decision: str | None) -> str:
    return {
        "BOOK_NOW": "green",
        "ALREADY_BOOKED": "teal",
        "WAIT_UNTIL": "blue",
        "REVIEW_REQUIRED": "amber",
    }.get(str(decision or "").upper(), "slate")


def _quality_label(row: dict[str, Any]) -> str:
    status = str(row.get("data_quality_status") or "OK")
    if status == "DATE_CONFLICT":
        return "Date conflict"
    if status == "MISSING_EXPIRY":
        return "Missing expiry"
    return "Valid"


def _deduction_table(analysis: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    small = ParagraphStyle(
        "CdasReportTableSmall",
        parent=styles["body_small"],
        fontSize=6.4,
        leading=8.2,
        textColor=colors.HexColor("#172033"),
    )
    small_right = ParagraphStyle(
        "CdasReportTableSmallRight",
        parent=small,
        alignment=2,
    )
    header = ParagraphStyle(
        "CdasReportTableHeader",
        parent=small,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        fontSize=6.2,
        leading=7.6,
    )

    rows: list[list[Any]] = [[
        Paragraph("Item", header),
        Paragraph("Agency", header),
        Paragraph("Deduction", header),
        Paragraph("Effective", header),
        Paragraph("Expiry", header),
        Paragraph("Reference", header),
        Paragraph("Quality", header),
    ]]
    row_tones: list[tuple[int, colors.Color]] = []
    for index, deduction in enumerate(analysis.get("deductions") or [], start=1):
        quality = _quality_label(deduction)
        rows.append([
            Paragraph(_text(deduction.get("item_code")), small),
            Paragraph(_text(deduction.get("agency_name")), small),
            Paragraph(_text(money_text(deduction.get("deduction_amount"))), small_right),
            Paragraph(_text(_date_text(deduction.get("effective_date"))), small),
            Paragraph(_text(_date_text(deduction.get("expiry_date"), "Not supplied")), small),
            Paragraph(_text(deduction.get("reference_no")), small),
            Paragraph(_text(quality), small),
        ])
        if deduction.get("data_quality_status") != "OK":
            row_tones.append((index, colors.HexColor("#FFF7E8")))
        elif deduction.get("is_own_booking"):
            row_tones.append((index, colors.HexColor("#ECFDF3")))

    if len(rows) == 1:
        rows.append([
            Paragraph("—", small),
            Paragraph("No deduction rows were available in this analysis.", small),
            "", "", "", "", "",
        ])

    widths = [14, 43, 22, 21, 21, 34, 19]
    table = Table(
        rows,
        colWidths=[value * mm for value in widths],
        repeatRows=1,
        hAlign="LEFT",
    )
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2742")),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]
    for row_index, background in row_tones:
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), background))
    table.setStyle(TableStyle(commands))
    return table


def _company_contact(company: LoanCompany) -> str:
    parts = [
        str(value).strip()
        for value in (company.phone, company.email, company.website)
        if value and str(value).strip()
    ]
    return " | ".join(parts) or "Not recorded"


def _company_address(company: LoanCompany) -> str:
    parts = [
        str(value).strip()
        for value in (company.address, company.district)
        if value and str(value).strip()
    ]
    return ", ".join(parts) or "Not recorded"


def _report_reference(
    analysis: dict[str, Any],
    opportunity_id: UUID | None,
) -> str:
    as_of = str(analysis.get("as_of") or "").replace("-", "")[:8]
    if not as_of or len(as_of) != 8:
        as_of = datetime.now(timezone.utc).strftime("%Y%m%d")
    if opportunity_id:
        return f"CDAS-{as_of}-{str(opportunity_id)[:8].upper()}"
    return f"CDAS-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-ANALYSIS"


def cdas_report_filename(client_name: str | None, reference: str) -> str:
    base = "".join(
        character if character.isalnum() else "-"
        for character in str(client_name or "CDAS-client")
    )
    while "--" in base:
        base = base.replace("--", "-")
    base = base.strip("-")[:50] or "CDAS-client"
    return f"{reference}-{base}.pdf"


def build_cdas_analysis_pdf(
    *,
    db: Session | None,
    company: LoanCompany,
    analysis: dict[str, Any],
    prepared_by_name: str,
    prepared_by_role: str,
    client_name: str | None = None,
    client_reference: str | None = None,
    opportunity_id: UUID | None = None,
) -> tuple[bytes, str]:
    """Build a formal tenant-company CDAS analysis report using LoanHub's PDF system.

    The tenant company is the issuer. LoanHub is identified as the generating
    platform. The report consumes only structured analysis data; raw pasted CDAS
    screen text is deliberately not embedded in the document.
    """

    styles = document_styles()
    profile = analysis.get("profile") or {}
    capacity = analysis.get("capacity") or {}
    booking_term = analysis.get("booking_term") or {}
    retirement = analysis.get("retirement_analysis") or {}
    application = analysis.get("application_context") or {}
    decision = str(analysis.get("decision") or "REVIEW_REQUIRED")
    decision_tone = _decision_tone(decision)

    effective_client_name = (
        str(client_name or "").strip()
        or str(profile.get("full_name") or "").strip()
        or "CDAS client"
    )
    effective_client_reference = (
        str(client_reference or "").strip()
        or str(profile.get("employee_no") or profile.get("nid") or "").strip()
        or "Not recorded"
    )
    current_agency_name = (
        application.get("current_cdas_agency_name")
        or application.get("new_deduction_agency_name")
    )
    current_agency_code = (
        application.get("current_cdas_agency_code")
        or application.get("new_deduction_agency_code")
    )
    reference = _report_reference(analysis, opportunity_id)
    generated_at = datetime.now(timezone.utc)

    story: list[Any] = []
    story.extend(hero_block(
        "CDAS Analysis Report",
        (
            f"Formal payroll-deduction capacity and booking analysis issued by "
            f"{_text(company.name)} from the structured CDAS information supplied for this client."
        ),
        reference,
        status=decision,
        styles=styles,
    ))

    issuer_card = detail_card(
        "Issuer and document control",
        [
            ("Issued by", _text(company.name)),
            ("Registration", _text(company.registration_number)),
            ("Licence", _text(company.license_number)),
            ("Prepared by", _text(prepared_by_name)),
            ("Active role", _text(humanize(prepared_by_role))),
            ("Analysis date", _text(_date_text(analysis.get("as_of")))),
        ],
        tone="blue",
    )
    client_card = detail_card(
        "Client and CDAS identity",
        [
            ("Client", _text(effective_client_name)),
            ("Client reference", _text(effective_client_reference)),
            ("National ID", _text(profile.get("nid"))),
            ("Employer", _text(profile.get("employer"))),
            ("CDAS agency", _text(current_agency_name)),
            ("Agency code", _text(current_agency_code)),
        ],
        tone="slate",
    )
    story.append(two_card_row(issuer_card, client_card))
    story.append(Spacer(1, 4 * mm))

    story.extend(section(
        "Analysis recommendation",
        "The recommendation combines the configured booking window, detected own-agency bookings, CDAS data quality and the assessed available deduction amount.",
        styles=styles,
    ))
    story.append(callout(
        humanize(decision),
        _text(analysis.get("decision_message"), "No recommendation message was recorded."),
        tone=decision_tone,
        styles=styles,
    ))
    story.append(Spacer(1, 3 * mm))

    assessed = capacity.get("assessed_available_amount")
    if assessed is None:
        assessed = capacity.get("max_available_after_selected_deductions")
    if assessed is None:
        assessed = capacity.get("max_available_deduction_amount")
    booking_allowed = bool(capacity.get("booking_allowed"))
    shortfall = capacity.get("shortfall_amount") or 0
    story.extend(section(
        "Deduction capacity",
        "Capacity values come from CDAS. Where a consolidation-after-selected figure is supplied, LoanHub uses it as the assessed amount.",
        styles=styles,
    ))
    story.append(metric_grid([
        (
            "Current max available",
            money_text(capacity.get("max_available_deduction_amount")),
            "Current CDAS payroll capacity",
            "red" if (capacity.get("max_available_deduction_amount") or 0) < 0 else "blue",
        ),
        (
            "After selected deductions",
            money_text(capacity.get("max_available_after_selected_deductions")) if capacity.get("max_available_after_selected_deductions") is not None else "Not supplied",
            "Used for consolidation when supplied",
            "teal",
        ),
        (
            "Assessed available",
            money_text(assessed) if assessed is not None else "Not recorded",
            "Amount used by the booking-capacity rule",
            "green" if booking_allowed else "amber",
        ),
        (
            "Capacity decision",
            "BOOK NOW" if booking_allowed else "USE BOOKING RULES",
            f"Threshold: greater than {money_text(capacity.get('booking_threshold_amount') or 1)}",
            "green" if booking_allowed else "amber",
        ),
        (
            "Shortfall",
            money_text(shortfall),
            "Excess over the allowed payroll deduction limit",
            "red" if shortfall else "slate",
        ),
        (
            "Next booking date",
            _date_text(analysis.get("next_possible_booking_date"), "Not applicable"),
            f"Configured lead: {analysis.get('booking_lead_months', 0)} month(s)",
            "blue",
        ),
    ], columns=2, styles=styles))

    amount_owing = booking_term.get("amount_owing")
    months_required = booking_term.get("months_required")
    monthly_capacity = booking_term.get("monthly_available_deduction")
    if amount_owing is not None or months_required is not None:
        story.extend(section(
            "Booking-term calculation",
            "When booking is allowed by positive capacity, the amount owing is divided by the assessed monthly deduction and rounded up to a whole month.",
            styles=styles,
        ))
        story.append(metric_grid([
            ("Amount owing", money_text(amount_owing), "Client amount supplied for term calculation", "slate"),
            ("Monthly available", money_text(monthly_capacity), "Maximum monthly capacity used", "green"),
            ("Minimum booking term", f"{months_required} month(s)" if months_required else "Not calculated", "Rounded up to a whole month", "teal"),
        ], columns=3, styles=styles))
        if months_required and monthly_capacity:
            story.append(callout(
                "Term formula",
                f"{_text(money_text(amount_owing))} owing ÷ {_text(money_text(monthly_capacity))} monthly capacity = <b>{months_required} month(s)</b> after rounding up.",
                tone="green",
                styles=styles,
            ))

    story.extend(section(
        "Client employment and retirement context",
        "These fields are reproduced only when they were present in the copied CDAS information.",
        styles=styles,
    ))
    personal_card = detail_card(
        "Personal profile",
        [
            ("Employee no.", _text(profile.get("employee_no"))),
            ("Gender", _text(profile.get("gender"))),
            ("Date of birth", _text(_date_text(profile.get("date_of_birth")))),
            ("National ID", _text(profile.get("nid"))),
        ],
        tone="slate",
    )
    employment_card = detail_card(
        "Employment and retirement",
        [
            ("Joining date", _text(_date_text(profile.get("joining_date")))),
            ("End date", _text(_date_text(profile.get("end_date")))),
            ("Early retirement", _text(_date_text(retirement.get("early_retirement_date") or profile.get("early_retirement_date")))),
            ("Compulsory retirement", _text(_date_text(retirement.get("compulsory_retirement_date") or profile.get("compulsory_retirement_date")))),
        ],
        tone="slate",
    )
    story.append(two_card_row(personal_card, employment_card))
    story.append(Spacer(1, 4 * mm))

    story.extend(section(
        "Deduction portfolio",
        "Reported Active amounts are separated from rows that LoanHub can safely use for booking timing.",
        styles=styles,
    ))
    deductions = analysis.get("deductions") or []
    story.append(metric_grid([
        ("Reported active", money_text(analysis.get("reported_active_monthly_deductions")), "All CDAS rows reported Active", "blue"),
        ("Booking-valid", money_text(analysis.get("total_monthly_deductions")), "Rows safe for booking calculations", "green"),
        ("Own agency", money_text(analysis.get("own_monthly_deductions")), "Detected as this tenant's booking", "teal"),
        ("Other agencies", money_text(analysis.get("competitor_monthly_deductions")), "Valid active competitor deductions", "slate"),
        ("Excluded / review", money_text(analysis.get("excluded_monthly_deductions")), "Retained financially but excluded from timing", "amber"),
        ("Deduction rows", str(len(deductions)), "Structured rows in this analysis", "slate"),
    ], columns=2, styles=styles))
    story.append(_deduction_table(analysis, styles))

    issues = analysis.get("data_quality_issues") or []
    if issues:
        story.extend(section(
            "CDAS data-quality findings",
            "Flagged rows remain visible in this report but are not used to create unsafe booking dates.",
            styles=styles,
        ))
        for issue in issues:
            title = f"Item {_text(issue.get('item_code'))} — {_text(issue.get('agency_name'))}"
            message = _text(issue.get("data_quality_message"), _quality_label(issue))
            story.append(callout(title, message, tone="amber", styles=styles))
            story.append(Spacer(1, 2 * mm))

    story.extend(section("Methodology and document control", styles=styles))
    story.append(callout(
        "Capacity rule",
        "An assessed Max Available Deduction Amount strictly greater than LSL 1.00 permits a BOOK NOW capacity decision, except where the client is already booked by the tenant's own agency. At LSL 1.00 or below, normal expiry and booking-window rules remain in force.",
        tone="blue",
        styles=styles,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(callout(
        "Structured source record",
        "This report is generated from the structured CDAS analysis snapshot. The original pasted CDAS screen text is not embedded in this report. Missing or contradictory expiry information is retained for financial visibility but excluded from booking-date calculations.",
        tone="slate",
        styles=styles,
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(callout(
        "Decision-support notice",
        f"This report is issued by {_text(company.name)} and generated via LoanHub. CDAS deduction capacity or a BOOK NOW result is not, by itself, final credit approval. The company must still apply its lending policy, affordability, identity, contractual and regulatory checks and verify material information against the source CDAS record.",
        tone="amber",
        styles=styles,
    ))
    story.append(Spacer(1, 4 * mm))

    final_card = detail_card(
        "Tenant-company report record",
        [
            ("Issuer", _text(company.name)),
            ("Prepared by", _text(prepared_by_name)),
            ("Role", _text(humanize(prepared_by_role))),
            ("Company contact", _text(_company_contact(company))),
            ("Company address", _text(_company_address(company))),
            ("Generated", generated_at.strftime("%d %B %Y %H:%M UTC")),
            ("Document status", "System-generated tenant report"),
        ],
        tone="blue",
        width=CONTENT_WIDTH,
        styles=styles,
    )
    story.append(final_card)

    context = DocumentContext(
        db=db,
        company=company,
        title="CDAS Analysis Report",
        reference=reference,
        footer_note=generated_timestamp(),
        confidential=True,
    )
    pdf = build_document(
        story=story,
        context=context,
        title=f"CDAS analysis - {effective_client_name}",
        author=f"{company.name} via LoanHub",
        subject="CDAS payroll deduction capacity and booking analysis",
    )
    return pdf, reference
