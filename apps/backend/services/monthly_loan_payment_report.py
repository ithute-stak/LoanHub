"""Company-scoped monthly loan repayment register, rendered with LoanHub PDF branding."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, Spacer, TableStyle
from sqlalchemy.orm import Session

from database.models.payment import PaymentTransaction
from services.pdf_design_system import (
    DocumentContext, build_document, callout, document_styles,
    hero_block, metric_grid, money_text, section,
)


def render_monthly_loan_payments(
    db: Session,
    *,
    company,
    month: str,
    payments: list[PaymentTransaction],
    timezone_name: str,
) -> bytes:
    """Only successful inbound repayments should be passed by the scoped router."""
    from zoneinfo import ZoneInfo

    styles = document_styles()
    zone = ZoneInfo(timezone_name)
    month_title = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    rows = sorted(payments, key=lambda p: (p.completed_at or datetime.min, str(p.id)))
    total = sum((Decimal(str(p.amount)) for p in rows), Decimal("0.00"))
    refs = {p.loan_id for p in rows if p.loan_id}
    story = hero_block(
        "Monthly Loan Payment Report",
        "Confirmed borrower repayments received during the selected calendar month; disbursements, unsuccessful and reversed transactions excluded.",
        month_title,
        styles=styles,
    )
    story.append(Spacer(1, 5 * mm))
    story.append(metric_grid([
        ("Total received", money_text(total), "Successful repayments", "green"),
        ("Payments", str(len(rows)), "Confirmed ledger transactions", "blue"),
        ("Loans", str(len(refs)), "Distinct loans", "teal"),
    ], columns=3, styles=styles))
    story.extend(section("Payment register", "Figures represent actual received payments, not scheduled instalment amounts.", styles=styles))
    cell = ParagraphStyle("MonthlyPaymentCell", parent=styles["body"], fontSize=7, leading=10)
    bold = ParagraphStyle("MonthlyPaymentHeader", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
    def para(v, style=cell):
        return Paragraph(escape(str(v or "—")), style)

    table_rows = [[para(v, bold) for v in ("Date", "Loan / folio", "Reference", "Method", "Amount (LSL)")]]
    for p in rows:
        timestamp = p.completed_at
        if timestamp and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        local_date = timestamp.astimezone(zone).strftime("%d %b %Y") if timestamp else "—"
        loan = p.loan
        identity = (getattr(loan, "folio_number", None) or getattr(loan, "loan_reference", None) or str(p.loan_id))
        reference = p.provider_reference or p.proof_reference or str(p.id)
        method = getattr(p.payment_method, "value", p.payment_method)
        table_rows.append([
            para(local_date), para(identity), para(reference),
            para(str(method).replace("_", " ").title()),
            para(f"{Decimal(str(p.amount)):,.2f}"),
        ])
    if not rows:
        table_rows.append([para("No successful repayments recorded"), "", "", "", ""])
    table_rows.append([para("TOTAL", bold), "", "", "", para(f"{total:,.2f}", bold)])
    table = LongTable(table_rows, colWidths=[26*mm, 42*mm, 52*mm, 28*mm, 26*mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153A64")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#153A64")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F1F5FA")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#153A64")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 4*mm))
    story.append(callout(
        "Audit note",
        "Payment dates reflect the confirmed transaction completion time in the company reporting timezone. This report excludes pending, failed, cancelled and reversed payments.",
        tone="blue", styles=styles,
    ))
    return build_document(
        story=story,
        context=DocumentContext(db=db, company=company, title="Monthly Loan Payment Report", reference=month_title),
        title=f"Monthly Loan Payment Report - {month_title}",
        subject="Confirmed monthly loan repayments",
    )
