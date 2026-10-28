"""PostgreSQL concurrent rollover idempotency and atomicity regression.

Uses mapped production ledger models in a disposable schema. It deliberately
does not call the disabled live posting and reversal entry points.
"""
import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_compensation import LoanRolloverCompensation


def _transfer(*, company, parent, child, source, user, reference):
    return LoanRolloverTransfer(
        company_id=company, parent_loan_id=parent, child_loan_id=child,
        source_installment_id=source, posted_by_user_id=user,
        transfer_reference=reference, agreement_reference="TEST-AGREEMENT",
        approval_reference="TEST-APPROVAL", principal_component=Decimal("60"),
        interest_component=Decimal("20"), fee_component=Decimal("10"),
        transfer_amount=Decimal("90"), status="posted", evidence={},
    )


def test_concurrent_transfer_cannot_duplicate_parent_receivable():
    dsn = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN not configured")
    engine = create_engine(dsn, pool_size=3, max_overflow=0)
    schema = "rollover_concurrent_" + uuid4().hex[:12]
    company, user, parent, child1, child2, source = (uuid4() for _ in range(6))
    try:
        # Schema creation must commit so both independent DB sessions can see it.
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            for table in ("loan_companies", "users", "client_company_loan", "repayment_installments"):
                conn.execute(text(f'CREATE TABLE "{table}" (id uuid PRIMARY KEY)'))
            for table, ids in (
                ("loan_companies", [company]), ("users", [user]),
                ("client_company_loan", [parent, child1, child2]),
                ("repayment_installments", [source]),
            ):
                for identity in ids:
                    conn.execute(text(f'INSERT INTO "{table}" (id) VALUES (:id)'), {"id": identity})
            LoanRolloverTransfer.__table__.create(bind=conn)
            LoanRolloverCompensation.__table__.create(bind=conn)
        with engine.connect() as first, engine.connect() as second:
            first.execute(text(f'SET search_path TO "{schema}"'))
            second.execute(text(f'SET search_path TO "{schema}"'))
            first.commit()
            second.commit()
            with Session(bind=first, expire_on_commit=False) as a:
                a.add(_transfer(company=company, parent=parent, child=child1,
                                source=source, user=user, reference="FIRST"))
                a.flush()  # Hold the unique parent index entry uncommitted.
                with Session(bind=second, expire_on_commit=False) as competing:
                    competing.execute(text("SET LOCAL lock_timeout = '400ms'"))
                    competing.add(_transfer(company=company, parent=parent, child=child2,
                                            source=source, user=user, reference="SECOND"))
                    with pytest.raises(OperationalError):
                        competing.flush()
                    competing.rollback()
                # Commit only after the competitor has been blocked by the index.
                a.commit()
            with Session(bind=second) as retry:
                retry.add(_transfer(company=company, parent=parent, child=child2,
                                    source=source, user=user, reference="SECOND"))
                with pytest.raises(IntegrityError):
                    retry.flush()
                retry.rollback()
            with Session(bind=first) as verify:
                records = verify.query(LoanRolloverTransfer).all()
                assert len(records) == 1
                assert records[0].child_loan_id == child1
                assert records[0].transfer_amount == Decimal("90")
                assert verify.query(LoanRolloverCompensation).count() == 0
    finally:
        try:
            with engine.begin() as clean:
                clean.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            engine.dispose()
