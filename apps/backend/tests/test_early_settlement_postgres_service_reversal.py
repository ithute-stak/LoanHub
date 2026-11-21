"""Service-level PostgreSQL reversal test using disposable mapped tables.

Runs the actual reverse_early_settlement function with real SQLAlchemy sessions.
Never uses LoanHub production tables; requires disposable CI PostgreSQL URL.
"""
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from database.models.enums import InstallmentStatus, LoanStatus
from services import early_settlement_service as service


def test_reversal_service_restores_cents_and_transaction_rollback(monkeypatch):
    url = os.getenv("LOANHUB_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL URL required")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        pytest.fail("Only PostgreSQL is supported")
    prefix = "reversal_probe_" + uuid4().hex
    Base = declarative_base()

    class Loan(Base):
        __tablename__ = prefix + "_loans"
        id = Column(UUID(as_uuid=True), primary_key=True)
        status = Column(String, nullable=False)
        total_repayable = Column(Numeric(15, 2))
        amount_paid = Column(Numeric(15, 2))
        balance = Column(Numeric(15, 2))
        maturity_date = Column(Date)
        repayment_period = Column(Integer)
        installment_amount = Column(Numeric(15, 2))
        calculation_breakdown = Column(JSONB)
        installments = relationship("Installment", back_populates="loan")

    class Installment(Base):
        __tablename__ = prefix + "_installments"
        id = Column(UUID(as_uuid=True), primary_key=True)
        loan_id = Column(UUID(as_uuid=True), ForeignKey(Loan.id))
        status = Column(String, nullable=False)
        paid_amount = Column(Numeric(15, 2))
        paid_at = Column(DateTime(timezone=True))
        is_superseded = Column(String)
        superseded_at = Column(DateTime(timezone=True))
        loan = relationship("Loan", back_populates="installments")

    class Quote(Base):
        __tablename__ = prefix + "_quotes"
        id = Column(UUID(as_uuid=True), primary_key=True)
        loan_id = Column(UUID(as_uuid=True), nullable=False)
        status = Column(String, nullable=False)
        original_total_repayable = Column(Numeric(15, 2))
        original_amount_paid = Column(Numeric(15, 2))
        original_balance = Column(Numeric(15, 2))
        original_maturity_date = Column(Date)
        original_term_months = Column(Integer)
        calculation_snapshot = Column(JSONB)
        installment_snapshot = Column(JSONB)
        reversed_at = Column(DateTime(timezone=True))

    engine = create_engine(url, pool_pre_ping=True)
    loan_id, installment_id, quote_id = uuid4(), uuid4(), uuid4()
    try:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        with Session.begin() as db:
            db.add(Loan(
                id=loan_id, status="completed", total_repayable=1000,
                amount_paid=1000, balance=0, maturity_date=date(2026, 11, 1),
                repayment_period=1, installment_amount=1000,
                calculation_breakdown={"early_settlement": True},
            ))
            db.add(Installment(
                id=installment_id, loan_id=loan_id, status="waived",
                paid_amount=Decimal("0.08"), is_superseded="yes",
            ))
            db.add(Quote(
                id=quote_id, loan_id=loan_id, status="settled",
                original_total_repayable=1500, original_amount_paid=500,
                original_balance=1000, original_maturity_date=date(2027, 1, 15),
                original_term_months=6,
                calculation_snapshot={"loan_snapshot": {
                    "status": "active", "total_repayable": "1500.00",
                    "amount_paid": "500.00", "balance": "1000.00",
                    "maturity_date": "2027-01-15", "repayment_period": 6,
                    "installment_amount": "250.00",
                    "calculation_breakdown": {"source": "legacy_cashout_book"},
                }},
                installment_snapshot=[{
                    "id": str(installment_id), "status": "partially_paid",
                    "paid_amount": "0.08", "paid_at": None,
                    "is_superseded": False, "superseded_at": None,
                }],
            ))

        monkeypatch.setattr(service, "LoanEarlySettlement", Quote)
        monkeypatch.setattr(service, "ClientCompanyLoan", Loan)
        monkeypatch.setattr(service, "_quote_from_payment", lambda db, payment: db.get(Quote, quote_id))

        # A successful reversal is fully persisted.
        with Session.begin() as db:
            assert service.reverse_early_settlement(db, SimpleNamespace()) is True
        with Session() as db:
            loan = db.get(Loan, loan_id)
            installment = db.get(Installment, installment_id)
            quote = db.get(Quote, quote_id)
            assert quote.status == "reversed"
            assert loan.status == LoanStatus.ACTIVE.value
            assert loan.amount_paid == Decimal("500.00")
            assert installment.status == InstallmentStatus.PARTIALLY_PAID.value
            assert installment.paid_amount == Decimal("0.08")
            assert installment.is_superseded == "false" or installment.is_superseded == "False"
            assert service.reverse_early_settlement(db, SimpleNamespace()) is False
            db.rollback()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
