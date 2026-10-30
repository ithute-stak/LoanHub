from __future__ import annotations

from html import escape
from typing import Any
from datetime import date
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle
from sqlalchemy.orm import Session
from core.access_control import TenantContext
from services.pdf_design_system import (
    BORDER, NAVY, DocumentContext, build_document, document_styles,
    generated_timestamp, hero_block, metric_grid, money_text, section,
)


def build_folio_due_pdf(
    *, db: Session, context: TenantContext, rows: list[dict[str, Any]],
    group_code: str | None, through_date: date,
) -> bytes:
    styles = document_styles()
    story: list[Any] = []
    group = group_code or "All work groups"
    story.extend(hero_block(
        "Due Instalments by Folio",
        f"Outstanding instalments due on or before {through_date.isoformat()}. "
        "Includes unpaid portions of instalments; excludes future dues.",
        f"LoanHub | {group}", styles=styles,
    ))
    total = sum(float(row.get("due_amount") or 0) for row in rows)
    story.append(metric_grid([
        ("Loans due", str(len(rows)), group, "teal"),
        ("Total due", money_text(total), "Unpaid instalment portions", "amber"),
    ], columns=2, styles=styles))
    story.extend(section("Due loan register",
        "Folio, borrower, occupation and contact information for collections follow-up.",
        styles=styles))
    def cell(value: object) -> Paragraph:
        return Paragraph(escape(str(value if value not in (None, "") else "Not recorded")), styles["body_small"])
    data: list[list[Any]] = [["Folio", "Name / surname", "Occupation", "Contacts", "Due date", "Due instalment"]]
    for row in rows:
        data.append([
            cell(row.get("folio_number") or row.get("loan_reference")),
            cell(row.get("borrower_name")),
            cell(row.get("occupation")),
            cell(row.get("contact_phone")),
            cell(row.get("due_date")),
            money_text(row.get("due_amount") or 0),
        ])
    if not rows:
        data.append([cell("No unpaid instalments due for this selection"), "", "", "", "", ""])
    table = Table(data, colWidths=[32*mm, 42*mm, 34*mm, 27*mm, 22*mm, 28*mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 7),
        ("FONTSIZE", (0,1), (-1,-1), 6.5),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F6F8FB")]),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, BORDER),
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
            title="Due Instalments by Folio",
            reference=f"{group} | Due through {through_date.isoformat()}",
            footer_note=generated_timestamp(), confidential=True,
        ),
        title="LoanHub Folio Due Instalments",
    )
