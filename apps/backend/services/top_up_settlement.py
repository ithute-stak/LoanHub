"""Auditable replacement-loan principal using LoanHub's existing settlement engine."""
from __future__ import annotations
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from database.models.client_loan_company import ClientCompanyLoan
from services.early_settlement_service import quote_early_settlement
from utils.payment_dates import current_payment_date


def preview_top_up_settlement(db: Session, *, loan: ClientCompanyLoan, actor_user_id):
    """Read-only quote: no early-settlement record is committed or superseded."""
    quote = quote_early_settlement(
        db, loan=loan, settlement_date=current_payment_date(),
        quoted_by_user_id=actor_user_id, persist=False,
    )
    if quote.overpayment_credit and quote.overpayment_credit > 0:
        raise HTTPException(409, "Credit balance requires manual settlement review")
    return quote


def replacement_principal(quote, cash_top_up: Decimal) -> Decimal:
    from services.early_settlement_service import money
    cash = money(cash_top_up)
    if cash <= 0:
        raise HTTPException(422, "Top-up cash must be greater than zero")
    return money(quote.settlement_amount + cash)
