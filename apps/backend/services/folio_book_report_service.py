from __future__ import annotations

from collections import defaultdict
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Spacer, Table, TableStyle

from core.access_control import TenantContext
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


def build_folio_book_pdf(
    *,
    context: TenantContext,
    rows: list[dict[str, Any]],
    integrity: dict[str, Any],
) -> bytes:
    styles = document_styles()
    story: list[Any] = []
    story.extend(hero_block(
        "Loan Folio Book",
        "Permanent loan-level sequence register. A folio belongs to the loan, not to the borrower. Each work group keeps an independent sequence book.",
        "Permanent sequence register",
        status="healthy" if integrity.get("healthy") else "attention required",
        styles=styles,
    ))
    story.append(metric_grid([
        ("Loans in book", str(integrity.get("loan_count", 0)), "All scoped loans", "blue"),
        ("Sequence books", str(len(integrity.get("groups") or [])), "One per work group", "teal"),
        ("Missing folios", str(integrity.get("missing_folio_count", 0)), "Must remain zero", "green" if not integrity.get("missing_folio_count") else "red"),
        ("Sequence gaps", str(integrity.get("gap_count", 0)), "Investigate any gap", "green" if not integrity.get("gap_count") else "amber"),
    ], columns=4, styles=styles))

    story.extend(section("Sequence control", "The next number shown below is informational. Loan creation remains the only authority that allocates a new folio, under the database concurrency lock.", styles=styles))
    control_data = [["Work group", "Loans", "First", "Last", "Next folio", "Gaps"]]
    for item in integrity.get("groups") or []:
        control_data.append([
            str(item.get("group_code") or ""),
            str(item.get("loan_count") or 0),
            str(item.get("first_sequence") or "-"),
            str(item.get("last_sequence") or "-"),
            str(item.get("next_folio") or ""),
            str(item.get("gap_count") or 0),
        ])
    control = Table(control_data, colWidths=[24*mm, 18*mm, 18*mm, 18*mm, 64*mm, 18*mm], repeatRows=1)
    control.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(control)
    story.append(Spacer(1, 4 * mm))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("group_code") or "GEN")].append(row)

    first_group = True
    for group_code, group_rows in sorted(grouped.items()):
        if not first_group:
            story.append(PageBreak())
        first_group = False
        story.extend(section(f"{group_code} sequence book", f"{len(group_rows)} loan(s), ordered by permanent sequence number.", styles=styles))
        data = [["Folio No.", "Borrower", "Loan Ref.", "Principal", "Balance", "Status"]]
        for row in sorted(group_rows, key=lambda item: int(item.get("sequence") or 0)):
            data.append([
                Paragraph(f"<b>{row.get('folio_number') or '-'}</b>", styles["body_small"]),
                Paragraph(str(row.get("borrower_name") or "Borrower"), styles["body_small"]),
                Paragraph(str(row.get("loan_reference") or "-"), styles["body_small"]),
                money_text(row.get("principal_amount") or 0),
                money_text(row.get("balance") or 0),
                str(row.get("status") or ""),
            ])
        table = Table(data, colWidths=[35*mm, 42*mm, 34*mm, 25*mm, 25*mm, 20*mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 6.7),
            ("FONTSIZE", (0, 1), (-1, -1), 6.5),
            ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
            ("ALIGN", (3, 1), (4, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(table)

    if not rows:
        story.append(Paragraph("No loans are currently available in this company/branch scope.", styles["body"]))

    return build_document(
        story=story,
        context=DocumentContext(
            db=None,
            company=context.company,
            title="Loan Folio Book",
            reference="Permanent loan sequence register",
            footer_note=generated_timestamp(),
            confidential=True,
        ),
        title="LoanHub Loan Folio Book",
        subject="Permanent loan-level folio sequence register",
    )
