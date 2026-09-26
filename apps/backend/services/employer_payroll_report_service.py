from __future__ import annotations

from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from database.models.employer_payroll import EmployerPayrollCycle
from services.employer_payroll_service import cycle_payload
from services.pdf_design_system import (
    BORDER,
    DocumentContext,
    NAVY,
    build_document,
    document_styles,
    generated_timestamp,
    hero_block,
    metric_grid,
    money_text,
    section,
)


def build_payroll_reconciliation_pdf(db: Session, cycle: EmployerPayrollCycle) -> bytes:
    payload = cycle_payload(cycle, include_lines=True)
    account = cycle.account
    group = account.employer_group if account else None
    group_code = group.code if group else "WORK GROUP"
    group_name = group.name if group else "Employer payroll"
    styles = document_styles()
    story: list[Any] = []
    story.extend(hero_block(
        "Employer Payroll Reconciliation",
        f"{group_name} ({group_code}) · payroll period {cycle.period_key}. Every matched loan is controlled by its permanent LoanHub folio number.",
        f"{group_code} · {cycle.period_key}",
        status=cycle.status,
        styles=styles,
    ))
    story.append(metric_grid([
        ("Expected", money_text(cycle.expected_amount), f"{cycle.expected_line_count} expected line(s)", "blue"),
        ("Received", money_text(cycle.actual_amount), f"{cycle.matched_line_count} matched line(s)", "teal"),
        ("Shortage", money_text(cycle.shortage_amount), "Missing/rejected/short lines", "red" if cycle.shortage_amount else "green"),
        ("Exceptions", str(cycle.exception_line_count), "Rows requiring attention", "amber" if cycle.exception_line_count else "green"),
    ], columns=4, styles=styles))
    story.extend(section(
        "Control summary",
        "Unmatched employer rows remain explicit exceptions. LoanHub does not silently guess a loan when a folio or employee number is ambiguous.",
        styles=styles,
    ))
    summary = Table([
        ["Scheduled pay date", cycle.scheduled_pay_date.isoformat(), "Collection channel", account.collection_channel if account else "-"],
        ["Excess received", money_text(cycle.excess_amount), "Rejected exposure", money_text(cycle.rejected_amount)],
        ["Payroll reference", account.payroll_reference or "Not recorded" if account else "Not recorded", "Tolerance", money_text(account.reconciliation_tolerance if account else 0)],
    ], colWidths=[31*mm, 53*mm, 31*mm, 53*mm])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F6F8FB")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F6F8FB")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.3),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(summary)
    story.append(Spacer(1, 4 * mm))
    story.extend(section("Deduction register", "Expected and actual deductions for the period, ordered by folio.", styles=styles))

    data: list[list[Any]] = [["Folio", "Borrower / employee", "Expected", "Actual", "Variance", "Result"]]
    for line in sorted(payload.get("deductions") or [], key=lambda row: str(row.get("folio_number") or "ZZZ")):
        employee = line.get("employee_number") or "No employee no."
        data.append([
            Paragraph(f"<b>{line.get('folio_number') or 'UNMATCHED'}</b>", styles["body_small"]),
            Paragraph(f"{line.get('borrower_name') or 'Unmatched row'}<br/><font color='#5E6B7A'>{employee}</font>", styles["body_small"]),
            money_text(line.get("expected_amount") or 0),
            money_text(line.get("actual_amount") or 0),
            money_text(line.get("variance_amount") or 0),
            str(line.get("status") or "").replace("_", " ").title(),
        ])
    table = Table(data, colWidths=[32*mm, 48*mm, 25*mm, 25*mm, 25*mm, 19*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 6.7),
        ("FONTSIZE", (0, 1), (-1, -1), 6.3),
        ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
        ("ALIGN", (2, 1), (4, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story.append(table)

    return build_document(
        story=story,
        context=DocumentContext(
            db=db,
            company=account.company if account else None,
            title="Employer Payroll Reconciliation",
            reference=f"{group_code} | {cycle.period_key}",
            footer_note=generated_timestamp(),
            confidential=True,
        ),
        title=f"LoanHub Employer Payroll Reconciliation - {group_code} {cycle.period_key}",
        subject="Employer payroll deduction reconciliation and exception register",
    )
