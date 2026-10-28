"""Rollback-only PostgreSQL lifecycle probe for a carried installment receivable.

Uses LoanHub's *actual* repayment-installment, transfer and compensation ORM
tables. Minimal loan/FK placeholders isolate the accounting conservation rule.
This is not an execution of the disabled production posting service.
"""
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateTable
from sqlalchemy.orm import Session

from database.models.enums import InstallmentStatus
from database.models.repayment import RepaymentInstallment
from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_compensation import LoanRolloverCompensation


def test_partial_final_installment_transfer_and_compensation_conserve_receivables():
    dsn = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration URL not configured")
    engine = create_engine(dsn)
    schema = "rollover_lifecycle_" + uuid4().hex[:12]
    company, actor, parent, child = (uuid4() for _ in range(4))
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                conn.execute(text('CREATE TABLE loan_companies (id uuid PRIMARY KEY)'))
                conn.execute(text('CREATE TABLE users (id uuid PRIMARY KEY)'))
                conn.execute(text('CREATE TABLE loan_renewal_cycles (id uuid PRIMARY KEY)'))
                conn.execute(text("""
                    CREATE TABLE client_company_loan (
                        id uuid PRIMARY KEY,
                        balance numeric(15,2) NOT NULL,
                        status text NOT NULL
                    )
                """))
                conn.execute(text('INSERT INTO loan_companies VALUES (:id)'), {"id":company})
                conn.execute(text('INSERT INTO users VALUES (:id)'), {"id":actor})
                conn.execute(text("""
                    INSERT INTO client_company_loan (id,balance,status) VALUES
                    (:parent,60.00,'ACTIVE'), (:child,0.00,'PENDING')
                """), {"parent":parent,"child":child})
                for model in (RepaymentInstallment, LoanRolloverTransfer, LoanRolloverCompensation):
                    conn.execute(CreateTable(model.__table__, include_foreign_key_constraints=None))
                with Session(bind=conn, expire_on_commit=False) as db:
                    source = RepaymentInstallment(
                        loan_id=parent, installment_number=1, due_date=__import__("datetime").date(2026,11,1),
                        principal_due=Decimal("100"), interest_due=Decimal("0"),
                        fee_due=Decimal("0"), total_due=Decimal("100"),
                        paid_amount=Decimal("40"), status=InstallmentStatus.PARTIALLY_PAID,
                        is_superseded=False,
                    )
                    db.add(source)
                    db.flush()
                    assert source.total_due - source.paid_amount == Decimal("60")
                    before = db.execute(text('SELECT SUM(balance) FROM client_company_loan')).scalar_one()
                    assert before == Decimal("60")
                    source.is_superseded = True
                    db.execute(text("UPDATE client_company_loan SET balance=0,status='COMPLETED' WHERE id=:id"), {"id":parent})
                    db.execute(text("UPDATE client_company_loan SET balance=60,status='ACTIVE' WHERE id=:id"), {"id":child})
                    child_row = RepaymentInstallment(
                        loan_id=child, installment_number=1, due_date=__import__("datetime").date(2026,12,1),
                        principal_due=Decimal("60"), interest_due=Decimal("0"), fee_due=Decimal("0"),
                        total_due=Decimal("60"), paid_amount=Decimal("0"),
                        status=InstallmentStatus.PENDING, is_superseded=False,
                    )
                    db.add(child_row)
                    transfer = LoanRolloverTransfer(
                        company_id=company, parent_loan_id=parent, child_loan_id=child,
                        source_installment_id=source.id, transfer_reference="LIFECYCLE-1",
                        agreement_reference="TEST-AGREEMENT", approval_reference="TEST-APPROVAL",
                        principal_component=Decimal("60"), interest_component=Decimal("0"),
                        fee_component=Decimal("0"), transfer_amount=Decimal("60"),
                        posted_by_user_id=actor, status="posted", evidence={"test":True},
                    )
                    db.add(transfer)
                    db.flush()
                    assert db.execute(text('SELECT SUM(balance) FROM client_company_loan')).scalar_one() == before
                    db.expire(source)
                    assert db.get(RepaymentInstallment, source.id).paid_amount == Decimal("40")
                    assert db.get(RepaymentInstallment, source.id).is_superseded is True

                    db.execute(text("UPDATE client_company_loan SET balance=60,status='ACTIVE' WHERE id=:id"), {"id":parent})
                    db.execute(text("UPDATE client_company_loan SET balance=0,status='CANCELLED' WHERE id=:id"), {"id":child})
                    source.is_superseded = False
                    child_row.is_superseded = True
                    db.add(LoanRolloverCompensation(
                        company_id=company, transfer_id=transfer.id,
                        reference="LIFECYCLE-UNDO-1", approval_reference="TEST-APPROVED-UNDO",
                        reason="rollback lifecycle simulation", amount=Decimal("60"),
                        principal_component=Decimal("60"), interest_component=Decimal("0"),
                        fee_component=Decimal("0"), approved_by_user_id=actor,
                        evidence={"no_cash_movement":True},
                    ))
                    db.flush()
                    assert db.execute(text('SELECT SUM(balance) FROM client_company_loan')).scalar_one() == before
                    db.expire_all()
                    assert db.get(RepaymentInstallment, source.id).paid_amount == Decimal("40")
                    assert db.get(RepaymentInstallment, source.id).is_superseded is False
                    assert db.get(RepaymentInstallment, child_row.id).is_superseded is True
                    assert db.query(LoanRolloverTransfer).count() == 1
                    assert db.query(LoanRolloverCompensation).count() == 1
            finally:
                outer.rollback()
    finally:
        engine.dispose()
