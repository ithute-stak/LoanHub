"""Auditable company loan cash-flow statement; never conflates cash movement with loan receivables."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, Spacer, TableStyle
from sqlalchemy.orm import Session

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from database.models.payment import PaymentTransaction
from database.models.client_loan_company import ClientCompanyLoan
from services.pdf_design_system import DocumentContext, build_document, hero_block, document_styles, metric_grid, money_text, section, callout


def statement_ledger(db: Session, *, company_id, branch_id, start_utc: datetime, end_utc: datetime):
    """Fetch posted loan cash movements up to period end, preserving opening-balance history."""
    query = (db.query(PaymentTransaction)
        .join(ClientCompanyLoan, PaymentTransaction.loan_id == ClientCompanyLoan.id)
        .filter(PaymentTransaction.company_id == company_id,
                ClientCompanyLoan.company_id == company_id,
                PaymentTransaction.status == PaymentStatus.SUCCEEDED,
                PaymentTransaction.completed_at.isnot(None),
                PaymentTransaction.completed_at < end_utc,
                PaymentTransaction.purpose.in_([PaymentPurpose.LOAN_REPAYMENT, PaymentPurpose.LOAN_DISBURSEMENT])))
    if branch_id is not None:
        query = query.filter(ClientCompanyLoan.branch_id == branch_id)
    return query.order_by(PaymentTransaction.completed_at, PaymentTransaction.id).all()


def build_period_statement(db: Session, *, company, period: str, start_utc: datetime,
                           end_utc: datetime, payments: list[PaymentTransaction], timezone_name: str) -> bytes:
    from zoneinfo import ZoneInfo
    zone = ZoneInfo(timezone_name)
    styles = document_styles()
    money_zero = Decimal("0.00")
    def amount(p): return Decimal(str(p.amount))
    def delta(p):
        if p.purpose == PaymentPurpose.LOAN_REPAYMENT and p.direction == PaymentDirection.INBOUND:
            return amount(p)
        if p.purpose == PaymentPurpose.LOAN_DISBURSEMENT and p.direction == PaymentDirection.OUTBOUND:
            return -amount(p)
        return money_zero
    prior = [p for p in payments if p.completed_at < start_utc]
    current = [p for p in payments if start_utc <= p.completed_at < end_utc]
    opening = sum((delta(p) for p in prior), money_zero)
    receipts = sum((amount(p) for p in current if delta(p) > 0), money_zero)
    disbursed = sum((-delta(p) for p in current if delta(p) < 0), money_zero)
    closing = opening + receipts - disbursed
    story = hero_block("Loan Cash Movement Statement",
        "Company lending cash-flow register — actual settled loan receipts and disbursements, not an accrual trial balance.",
        period, styles=styles)
    story.append(Spacer(1, 5*mm))
    story.append(metric_grid([
        ("Opening net cash movement", money_text(opening), "Cumulative recorded movements before period", "slate"),
        ("Loan repayments", money_text(receipts), "Received during period", "green"),
        ("Loan disbursements", money_text(disbursed), "Issued during period", "blue"),
        ("Closing net cash movement", money_text(closing), "Opening + receipts - disbursements", "teal"),
    ], columns=2, styles=styles))
    story.extend(section("Transaction register", "All amounts in LSL. Debit denotes cash paid out; credit denotes cash received.", styles=styles))
    style = ParagraphStyle("LoanCashStatementCell", parent=styles["body"], fontSize=7, leading=9)
    header = ParagraphStyle("LoanCashStatementHeader", parent=style, fontName="Helvetica-Bold", textColor=colors.white)
    def cell(value, s=style): return Paragraph(escape(str(value)), s)
    records = [[cell(t, header) for t in ("Date", "Folio / Loan", "Transaction reference", "Debit", "Credit", "Running net")]]
    running = opening
    for p in current:
        movement = delta(p)
        if not movement: continue
        running += movement
        when = p.completed_at.replace(tzinfo=timezone.utc).astimezone(zone).strftime("%d %b %Y")
        loan = p.loan
        folio = getattr(loan, "folio_number", None) or getattr(loan, "loan_reference", None) or str(p.loan_id)
        reference = p.provider_reference or p.proof_reference or str(p.id)
        records.append([cell(when), cell(folio), cell(reference), cell(f"{-movement:,.2f}" if movement < 0 else "—"),
                        cell(f"{movement:,.2f}" if movement > 0 else "—"), cell(f"{running:,.2f}")])
    if len(records) == 1:
        records.append([cell("No settled loan movements"), "", "", "", "", ""])
    records.append([cell("PERIOD TOTAL", header), "", "", cell(f"{disbursed:,.2f}", header),
                    cell(f"{receipts:,.2f}", header), cell(f"{closing:,.2f}", header)])
    table = LongTable(records, colWidths=[24*mm, 31*mm, 43*mm, 24*mm, 24*mm, 28*mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#153A64")),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#153A64")),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white,colors.HexColor("#F2F6FB")]),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 5*mm))
    story.append(callout("Accounting interpretation",
        "The opening and closing figures are cumulative net loan cash movements (receipts less disbursements), not bank balances, cash-on-hand, profit, loan book outstanding principal or general-ledger balances. Failed and reversed transactions are excluded. Reconcile separately against bank/cash and loan receivables ledgers.",
        tone="blue", styles=styles))
    return build_document(story=story, context=DocumentContext(db=db, company=company, title="Loan Cash Movement Statement", reference=period),
                          title=f"Loan Cash Movement Statement - {period}", subject="Period loan cash movement statement")
