"""Real mapped rollover-ledger PostgreSQL transaction invariants.

Uses the production SQLAlchemy table definitions and production-equivalent
append-only triggers, with minimal FK targets in a disposable schema.
No application loan balances are mutated and both posting gates remain closed.
"""
import os
from uuid import uuid4
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy.orm import Session

from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_compensation import LoanRolloverCompensation


def test_mapped_rollover_transfer_compensation_transaction_postgres():
    dsn = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration URL not configured")
    engine = create_engine(dsn)
    schema = "rollover_real_" + uuid4().hex[:12]
    company, actor, parent, child, installment = (uuid4() for _ in range(5))
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                for table in ("loan_companies", "users", "client_company_loan", "repayment_installments"):
                    conn.execute(text(f'CREATE TABLE "{table}" (id uuid PRIMARY KEY)'))
                conn.execute(text('INSERT INTO loan_companies (id) VALUES (:id)'), {"id": company})
                conn.execute(text('INSERT INTO users (id) VALUES (:id)'), {"id": actor})
                for key, ident in (("client_company_loan", parent), ("client_company_loan", child), ("repayment_installments", installment)):
                    conn.execute(text(f'INSERT INTO "{key}" (id) VALUES (:id)'), {"id": ident})

                # The CREATE TABLE statements are compiled from the actual
                # application ORM tables, not copied or hand-written DDL.
                conn.execute(CreateTable(LoanRolloverTransfer.__table__, include_foreign_key_constraints=None))
                conn.execute(CreateTable(LoanRolloverCompensation.__table__, include_foreign_key_constraints=None))
                conn.execute(text("""
                    CREATE FUNCTION prevent_rollover_transfer_mutation() RETURNS trigger
                    LANGUAGE plpgsql AS $$
                    BEGIN
                        RAISE EXCEPTION 'Rollover transfer ledger is append-only';
                    END;
                    $$
                """))
                for table in ("loan_rollover_transfers", "loan_rollover_compensations"):
                    conn.execute(text(f"""
                        CREATE TRIGGER trg_immutable BEFORE UPDATE OR DELETE ON "{table}"
                        FOR EACH ROW EXECUTE FUNCTION prevent_rollover_transfer_mutation()
                    """))

                with Session(bind=conn, expire_on_commit=False) as db:
                    transfer = LoanRolloverTransfer(
                        company_id=company, parent_loan_id=parent,
                        child_loan_id=child, source_installment_id=installment,
                        transfer_reference="TEST-TRANSFER", agreement_reference="TEST-AGREEMENT",
                        approval_reference="TEST-APPROVAL",
                        principal_component=Decimal("70"), interest_component=Decimal("20"),
                        fee_component=Decimal("10"), transfer_amount=Decimal("100"),
                        posted_by_user_id=actor, evidence={"test": True},
                    )
                    db.add(transfer)
                    db.flush()
                    compensation = LoanRolloverCompensation(
                        company_id=company, transfer_id=transfer.id, reference="TEST-REVERSAL",
                        approval_reference="TEST-APPROVAL-REVERSAL", reason="test only",
                        amount=Decimal("100"), principal_component=Decimal("70"),
                        interest_component=Decimal("20"), fee_component=Decimal("10"),
                        approved_by_user_id=actor, evidence={"test": True},
                    )
                    db.add(compensation)
                    db.flush()
                    assert db.get(LoanRolloverTransfer, transfer.id).transfer_amount == Decimal("100")
                    assert db.get(LoanRolloverCompensation, compensation.id).amount == Decimal("100")
                    assert db.query(LoanRolloverTransfer).count() == 1
                    assert db.query(LoanRolloverCompensation).count() == 1

                    for sql in (
                        'UPDATE loan_rollover_transfers SET transfer_amount=99',
                        'DELETE FROM loan_rollover_transfers',
                        'UPDATE loan_rollover_compensations SET amount=99',
                        'DELETE FROM loan_rollover_compensations',
                    ):
                        with pytest.raises(Exception, match="append-only"):
                            with db.begin_nested():
                                db.execute(text(sql))

                    with pytest.raises(IntegrityError):
                        with db.begin_nested():
                            db.add(LoanRolloverCompensation(
                                company_id=company, transfer_id=transfer.id, reference="DUPLICATE",
                                approval_reference="DUPLICATE", reason="duplicate", amount=Decimal("100"),
                                principal_component=Decimal("70"), interest_component=Decimal("20"),
                                fee_component=Decimal("10"), approved_by_user_id=actor,
                                evidence={},
                            ))
                            db.flush()

                    with pytest.raises(IntegrityError):
                        with db.begin_nested():
                            db.add(LoanRolloverTransfer(
                                company_id=company, parent_loan_id=uuid4(), child_loan_id=uuid4(),
                                source_installment_id=installment, transfer_reference="BAD-SUM",
                                agreement_reference="TEST", approval_reference="TEST",
                                transfer_amount=Decimal("100"), principal_component=Decimal("75"),
                                interest_component=Decimal("20"), fee_component=Decimal("10"),
                                posted_by_user_id=actor, evidence={},
                            ))
                            db.flush()
                    assert db.query(LoanRolloverTransfer).count() == 1
                    assert db.query(LoanRolloverCompensation).count() == 1
            finally:
                outer.rollback()
    finally:
        engine.dispose()
