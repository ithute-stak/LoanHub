"""Real PostgreSQL transaction regression for top-up settlement and reversal.

Exercises production gateway settlement and disbursement reversal functions with
small mapped tables in a rollback-only transaction. It never calls a payment
provider or touches the application's actual loan tables.
"""
import os
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import Boolean, DateTime, Enum, Numeric, String, Text, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from database.models.enums import LoanStatus, PaymentPurpose
from services import lelefa_paygate_service as gateway
from services import loan_service


class Base(DeclarativeBase):
    pass


class Loan(Base):
    __tablename__ = "topup_pg_test_loans"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[object] = mapped_column(Uuid, nullable=False)
    borrower_id: Mapped[object] = mapped_column(Uuid, nullable=False)
    parent_loan_id: Mapped[object | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[LoanStatus] = mapped_column(Enum(LoanStatus, native_enum=False), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_repayable: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    top_up_settlement_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    is_top_up: Mapped[bool] = mapped_column(Boolean, nullable=False)
    loan_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    disbursed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    disbursed_by_user_id: Mapped[object | None] = mapped_column(Uuid)


class Settlement(Base):
    __tablename__ = "topup_pg_test_settlements"
    id: Mapped[object] = mapped_column(Uuid, primary_key=True, default=uuid4)
    company_id: Mapped[object] = mapped_column(Uuid, nullable=False)
    borrower_id: Mapped[object] = mapped_column(Uuid, nullable=False)
    parent_loan_id: Mapped[object] = mapped_column(Uuid, nullable=False)
    new_loan_id: Mapped[object] = mapped_column(Uuid, nullable=False, unique=True)
    settlement_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    cash_to_borrower: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    parent_balance_before: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    parent_amount_paid_before: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    parent_status_before: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    settled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    settled_by_user_id: Mapped[object | None] = mapped_column(Uuid)
    reversed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    reversed_by_user_id: Mapped[object | None] = mapped_column(Uuid)
    notes: Mapped[str | None] = mapped_column(Text)


def test_postgres_gateway_topup_settle_reverse_and_replay(monkeypatch):
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN not configured")
    engine = create_engine(dsn)
    company, borrower = uuid4(), uuid4()
    monkeypatch.setattr(gateway, "ClientCompanyLoan", Loan)
    monkeypatch.setattr(gateway, "LoanTopUpSettlement", Settlement)
    monkeypatch.setattr(loan_service, "ClientCompanyLoan", Loan)
    monkeypatch.setattr(loan_service, "LoanTopUpSettlement", Settlement)
    monkeypatch.setattr(
        "services.top_up_settlement.preview_top_up_settlement",
        lambda *_args, **_kwargs: SimpleNamespace(
            settlement_amount=Decimal("1000.00"), calculation_method="micro_loan",
            unearned_interest_rebate=Decimal("320.00"),
        ),
    )
    monkeypatch.setattr(
        "services.early_settlement_service.reverse_early_settlement",
        lambda *_args, **_kwargs: False,
    )
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                Base.metadata.create_all(conn)
                with Session(bind=conn, expire_on_commit=False) as db:
                    parent = Loan(
                        id=uuid4(), company_id=company, borrower_id=borrower,
                        parent_loan_id=None, status=LoanStatus.ACTIVE,
                        balance=Decimal("1320.00"), amount_paid=Decimal("0"),
                        total_repayable=Decimal("1320"), principal_amount=Decimal("1000"),
                        top_up_settlement_amount=None, is_top_up=False, loan_reference="OLD",
                    )
                    replacement = Loan(
                        id=uuid4(), company_id=company, borrower_id=borrower,
                        parent_loan_id=parent.id, status=LoanStatus.APPROVED,
                        balance=Decimal("1584"), amount_paid=Decimal("0"),
                        total_repayable=Decimal("1584"), principal_amount=Decimal("1200"),
                        top_up_settlement_amount=Decimal("1000"), is_top_up=True,
                        loan_reference="TOP",
                    )
                    db.add_all((parent, replacement))
                    db.flush()
                    payment = SimpleNamespace(
                        loan=replacement, loan_id=replacement.id, amount=Decimal("200"),
                        completed_at=None, initiated_by_user_id=uuid4(),
                        purpose=PaymentPurpose.LOAN_DISBURSEMENT,
                        reversed_by_user_id=uuid4(),
                    )
                    gateway._finalize_top_up(db, payment)
                    db.flush()
                    db.expire_all()
                    assert db.get(Loan, parent.id).status == LoanStatus.COMPLETED
                    assert db.get(Loan, parent.id).balance == Decimal("0")
                    assert db.get(Loan, parent.id).amount_paid == Decimal("0")
                    settlement = db.query(Settlement).one()
                    assert settlement.settlement_amount == Decimal("1000")
                    assert settlement.cash_to_borrower == Decimal("200")
                    loan_service.reverse_loan_payment(db, payment)
                    db.flush()
                    db.expire_all()
                    restored = db.get(Loan, parent.id)
                    assert restored.balance == Decimal("1320")
                    assert restored.amount_paid == Decimal("0")
                    assert restored.status == LoanStatus.ACTIVE
                    assert db.query(Settlement).one().status == "reversed"
                    from fastapi import HTTPException
                    with pytest.raises(HTTPException) as exc:
                        gateway._finalize_top_up(db, payment)
                    assert exc.value.status_code == 409
                    assert db.query(Settlement).count() == 1
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
