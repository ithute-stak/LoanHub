from __future__ import annotations

from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from services.pdf_design_system import (
    BORDER, NAVY, DocumentContext, build_document, document_styles,
    generated_timestamp, hero_block, metric_grid, money_text, section,
)


def build_overdue_portfolio_pdf(
    *, db: Session, context: TenantContext, rows: list[dict[str, Any]]
) -> bytes:
    """Build an active-tenant, explicitly selected overdue portfolio report."""
    styles = document_styles()
    total_balance = sum(float(row.get("balance") or 0) for row in rows)
    story: list[Any] = []
    story.extend(hero_block(
        "Overdue Debt Register",
        "Filtered overdue loan portfolio for authorised collections and management use. "
        "Figures are a snapshot at generation time; verify balances before collection.",
        "LoanHub | Overdue debt report",
        status="Attention required", styles=styles,
    ))
    story.append(metric_grid([
        ("Overdue loans", str(len(rows)), "Selected and verified", "red"),
        ("Total outstanding", money_text(total_balance), "Loan balances", "amber"),
    ], columns=2, styles=styles))
    story.extend(section(
        "Overdue accounts",
        "All records below were checked against the current company's loan book. "
        "A listed balance is total outstanding, not necessarily the overdue installment amount.",
        styles=styles,
    ))
    data: list[list[Any]] = [[
        "Folio / loan", "Borrower", "Due date", "Installment", "Balance", "Status",
    ]]
    for row in rows:
        def paragraph(value: object) -> Paragraph:
            return Paragraph(escape(str(value or "-")), styles["body_small"])

        data.append([
            paragraph(row.get("folio_number") or row.get("loan_reference")),
            paragraph(row.get("borrower_name")),
            paragraph(row.get("due_date")),
            money_text(row.get("installment_amount") or 0),
            money_text(row.get("balance") or 0),
            paragraph("Overdue"),
        ])
    table = Table(
        data, colWidths=[38 * mm, 43 * mm, 25 * mm, 25 * mm, 27 * mm, 16 * mm],
        repeatRows=1, hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 6.7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "Confidential. For internal authorised debt management only. "
        "Amounts should be reconciled with repayments and charges before sending demands.",
        styles["body_small"],
    ))
    return build_document(
        story=story,
        context=DocumentContext(
            db=db,
            company=context.company,
            title="Overdue Debt Register",
            reference="Overdue loan portfolio | Filtered export",
            footer_note=generated_timestamp(),
            confidential=True,
        ),
        title="LoanHub Overdue Debt Register",
    )
