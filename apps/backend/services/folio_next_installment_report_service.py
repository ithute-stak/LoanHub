from __future__ import annotations

from html import escape
from typing import Any
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle
from sqlalchemy.orm import Session
from core.access_control import TenantContext
from services.pdf_design_system import (
    BORDER, NAVY, DocumentContext, build_document, document_styles,
    generated_timestamp, hero_block, metric_grid, money_text, section,
)


def build_folio_next_installment_pdf(
    *, db: Session, context: TenantContext, rows: list[dict[str, Any]],
    group_code: str | None, from_date: date | None, through_date: date | None,
    loan_from_date: date,
) -> bytes:
    styles = document_styles()
    story: list[Any] = []
    group = group_code or "All work groups"
    period = f"{from_date.isoformat() if from_date else 'Any date'} to {through_date.isoformat() if through_date else 'Any date'}"
    story.extend(hero_block(
        "Next Outstanding Instalment by Folio",
        f"Earliest unpaid instalment per loan disbursed from {loan_from_date.isoformat()}. Due date range: {period}. "
        "Includes overdue and future dues unless filtered.",
        f"LoanHub | {group}", styles=styles,
    ))
    total = sum(float(row.get("due_amount") or 0) for row in rows)
    story.append(metric_grid([
        ("Loans listed", str(len(rows)), group, "teal"),
        ("Next payments", money_text(total), "One outstanding instalment per loan", "amber"),
    ], columns=2, styles=styles))
    story.extend(section("Next-payment register",
        "Folio, borrower, occupation and contact information for collections follow-up.",
        styles=styles))
    def cell(value: object) -> Paragraph:
        return Paragraph(escape(str(value if value not in (None, "") else "Not recorded")), styles["body_small"])
    data: list[list[Any]] = [["Folio", "Name / surname", "Occupation", "Contacts", "Due date", "Due instalment", "Comments / follow-up"]]
    for row in rows:
        data.append([
            cell(row.get("folio_number") or row.get("loan_reference")),
            cell(row.get("borrower_name")),
            cell(row.get("occupation")),
            cell(row.get("contact_phone")),
            cell(row.get("due_date")),
            money_text(row.get("due_amount") or 0),
            Paragraph("________________________<br/>________________________", styles["body_small"]),
        ])
    if not rows:
        data.append([cell("No matching outstanding instalments"), "", "", "", "", "", ""])
    table = Table(data, colWidths=[32*mm, 43*mm, 34*mm, 31*mm, 24*mm, 30*mm, 64*mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 7),
        ("FONTSIZE", (0,1), (-1,-1), 6.5),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F6F8FB")]),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
        ("LINEBEFORE", (-1,0), (-1,-1), 0.8, BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(table)
    return build_document(
        story=story,
        context=DocumentContext(
            db=db, company=context.company,
            title="Next Outstanding Instalment by Folio",
            reference=f"{group} | Disbursed from {loan_from_date.isoformat()} | {period}",
            footer_note=generated_timestamp(), confidential=True,
        ),
        title="LoanHub Next Instalments",
        pagesize=landscape(A4),
    )
