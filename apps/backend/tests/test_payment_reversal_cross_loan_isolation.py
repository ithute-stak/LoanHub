"""Exact-loan and exact-tenant cash-reversal authorization regressions.

Synthetic in-memory rows only; no production database connections or writes.
Tests the real service's SQLAlchemy row-selection predicates before any
allocation, treasury, or accounting mutation can occur.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, Numeric, String, Uuid, create_engine
from sqlalchemy.orm import Session, declarative_base

import services.loan_last_payment_reversal as reversal


@pytest.mark.parametrize("foreign_company", [False, True])
def test_reversal_rejects_payment_from_another_loan_or_company(
    monkeypatch, foreign_company,
):
    base = declarative_base()

    class LoanRow(base):
        __tablename__ = "synthetic_reversal_loan"
        id = Column(Uuid(as_uuid=True), primary_key=True)
        company_id = Column(Uuid(as_uuid=True), nullable=False)
        balance = Column(Numeric(14, 2), nullable=False)
        amount_paid = Column(Numeric(14, 2), nullable=False)

    class PaymentRow(base):
        __tablename__ = "synthetic_reversal_payment"
        id = Column(Uuid(as_uuid=True), primary_key=True)
        company_id = Column(Uuid(as_uuid=True), nullable=False)
        loan_id = Column(Uuid(as_uuid=True), nullable=False)
        status = Column(String, nullable=False)

    company_a, company_b = uuid4(), uuid4()
    current_loan_id, legacy_loan_id, payment_id = uuid4(), uuid4(), uuid4()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    base.metadata.create_all(engine)
    monkeypatch.setattr(reversal, "ClientCompanyLoan", LoanRow)
    monkeypatch.setattr(reversal, "PaymentTransaction", PaymentRow)

    with Session(engine) as db:
        db.add_all([
            LoanRow(
                id=current_loan_id, company_id=company_a,
                balance=Decimal("900.00"), amount_paid=Decimal("100.00"),
            ),
            LoanRow(
                id=legacy_loan_id, company_id=company_a,
                balance=Decimal("0.00"), amount_paid=Decimal("1500.00"),
            ),
            PaymentRow(
                id=payment_id,
                company_id=company_b if foreign_company else company_a,
                loan_id=current_loan_id if foreign_company else legacy_loan_id,
                status="succeeded",
            ),
        ])
        db.commit()

        with pytest.raises(HTTPException) as caught:
            reversal.reverse_latest_cash_repayment(
                db, loan_id=current_loan_id, company_id=company_a,
                payment_id=payment_id, user_id=uuid4(),
                actor_role="company_owner",
                reason="Synthetic wrong loan repayment reversal denied",
            )
        assert caught.value.status_code == 404
        assert "Payment not found for this loan" in caught.value.detail

        # A denied reversal must not alter either loan or the payment.
        current = db.get(LoanRow, current_loan_id)
        legacy = db.get(LoanRow, legacy_loan_id)
        payment = db.get(PaymentRow, payment_id)
        assert (current.balance, current.amount_paid) == (
            Decimal("900.00"), Decimal("100.00"),
        )
        assert (legacy.balance, legacy.amount_paid) == (
            Decimal("0.00"), Decimal("1500.00"),
        )
        assert payment.status == "succeeded"
        assert payment.loan_id == (
            current_loan_id if foreign_company else legacy_loan_id
        )
    engine.dispose()
