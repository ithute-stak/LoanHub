"""Actual ORM PostgreSQL rollback regression for a failed rollover.

The test uses LoanHub's mapped repayment and transfer tables, inside an
isolated PostgreSQL schema. A deliberately rejected ledger record must roll
back the associated parent/child balance and installment supersession writes.
Production service posting remains disabled.
"""
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.enums import InstallmentStatus
from database.models.repayment import RepaymentInstallment
from database.models.loan_rollover_transfer import LoanRolloverTransfer


def test_failed_transfer_ledger_flush_rolls_back_loan_and_schedule_updates():
    dsn = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN not configured")
    engine = create_engine(dsn)
    schema = "rollover_atomic_" + uuid4().hex[:12]
    company, maker, parent, child = (uuid4() for _ in range(4))
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            connection.execute(text("CREATE TABLE loan_companies(id uuid PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE users(id uuid PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE loan_renewal_cycles(id uuid PRIMARY KEY)"))
            connection.execute(text(
                "CREATE TABLE client_company_loan("
                "id uuid PRIMARY KEY, balance numeric(15,2) NOT NULL, status text NOT NULL)"
            ))
            connection.execute(text("INSERT INTO loan_companies VALUES (:id)"), {"id": company})
            connection.execute(text("INSERT INTO users VALUES (:id)"), {"id": maker})
            connection.execute(
                text("INSERT INTO client_company_loan VALUES (:id, :balance, :status)"),
                {"id": parent, "balance": Decimal("60"), "status": "active"},
            )
            connection.execute(
                text("INSERT INTO client_company_loan VALUES (:id, :balance, :status)"),
                {"id": child, "balance": Decimal("0"), "status": "pending"},
            )
            RepaymentInstallment.__table__.create(bind=connection)
            LoanRolloverTransfer.__table__.create(bind=connection)
            with Session(bind=connection, expire_on_commit=False) as seed:
                installment = RepaymentInstallment(
                    loan_id=parent, installment_number=1, due_date=date(2026, 11, 1),
                    principal_due=Decimal("100"), interest_due=Decimal("0"),
                    fee_due=Decimal("0"), total_due=Decimal("100"),
                    paid_amount=Decimal("40"), status=InstallmentStatus.PARTIALLY_PAID,
                    is_superseded=False,
                )
                seed.add(installment)
                seed.flush()
                source_id = installment.id
            # A rejected CHECK constraint simulates failure after the other
            # balance/schedule operations have been staged and flushed.
            with Session(bind=connection) as session:
                with pytest.raises(IntegrityError):
                    with session.begin_nested():
                        session.execute(text(
                            "UPDATE client_company_loan SET balance=0, status='completed' WHERE id=:id"
                        ), {"id": parent})
                        session.execute(text(
                            "UPDATE client_company_loan SET balance=60, status='active' WHERE id=:id"
                        ), {"id": child})
                        source = session.get(RepaymentInstallment, source_id)
                        source.is_superseded = True
                        session.add(LoanRolloverTransfer(
                            company_id=company, parent_loan_id=parent,
                            child_loan_id=child, source_installment_id=source_id,
                            transfer_reference="REJECT-ATOMIC",
                            agreement_reference="TEST", approval_reference="TEST",
                            principal_component=Decimal("61"),
                            interest_component=Decimal("0"),
                            fee_component=Decimal("0"),
                            transfer_amount=Decimal("60"),
                            posted_by_user_id=maker, status="posted", evidence={},
                        ))
                        session.flush()
                session.expire_all()
                rows = connection.execute(
                    text("SELECT id,balance,status FROM client_company_loan")
                ).all()
                amounts = {row.id: row.balance for row in rows}
                assert amounts == {parent: Decimal("60"), child: Decimal("0")}
                restored = session.get(RepaymentInstallment, source_id)
                assert restored.is_superseded is False
                assert restored.paid_amount == Decimal("40")
                assert session.query(LoanRolloverTransfer).count() == 0
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
