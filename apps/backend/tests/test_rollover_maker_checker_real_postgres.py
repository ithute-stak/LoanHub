"""PostgreSQL certification gate: durable maker/checker database invariants.

Creates actual LoanHub mapped authorization tables and transfer ledger in an
isolated rollback-only schema. Neither production financial posting gate is
disabled by these tests. No production data or payment provider is touched.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.loan_rollover_transfer import LoanRolloverTransfer
from database.models.loan_rollover_reversal_request import LoanRolloverReversalRequest
from database.models.loan_rollover_reversal_approval import LoanRolloverReversalApproval


def test_real_mapped_maker_checker_postgresql_integrity():
    dsn = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN not configured")
    engine = create_engine(dsn)
    schema = "rollover_auth_" + uuid4().hex[:12]
    company, maker, checker, parent, child, installment = (uuid4() for _ in range(6))
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                for table in ("loan_companies", "users", "client_company_loan", "repayment_installments"):
                    conn.execute(text(f'CREATE TABLE "{table}" (id uuid PRIMARY KEY)'))
                conn.execute(text('INSERT INTO loan_companies (id) VALUES (:id)'), {"id": company})
                for identity in (maker, checker):
                    conn.execute(text('INSERT INTO users (id) VALUES (:id)'), {"id": identity})
                for identity in (parent, child):
                    conn.execute(text('INSERT INTO client_company_loan (id) VALUES (:id)'), {"id": identity})
                conn.execute(text('INSERT INTO repayment_installments (id) VALUES (:id)'), {"id": installment})
                for model in (LoanRolloverTransfer, LoanRolloverReversalRequest, LoanRolloverReversalApproval):
                    model.__table__.create(bind=conn)
                conn.execute(text("""
                    CREATE FUNCTION prevent_rollover_transfer_mutation() RETURNS trigger
                    LANGUAGE plpgsql AS $$
                    BEGIN
                      RAISE EXCEPTION 'Rollover authorization evidence is append-only';
                    END;
                    $$
                """))
                for table in ("loan_rollover_reversal_requests", "loan_rollover_reversal_approvals"):
                    conn.execute(text(f"""
                        CREATE TRIGGER trg_immutable BEFORE UPDATE OR DELETE ON "{table}"
                        FOR EACH ROW EXECUTE FUNCTION prevent_rollover_transfer_mutation()
                    """))
                with Session(bind=conn, expire_on_commit=False) as db:
                    transfer = LoanRolloverTransfer(
                        company_id=company, parent_loan_id=parent, child_loan_id=child,
                        source_installment_id=installment, transfer_reference="AUTH-TRANSFER",
                        agreement_reference="AUTH-AGREEMENT", approval_reference="AUTH-APPROVAL",
                        principal_component=90, interest_component=0, fee_component=0,
                        transfer_amount=90, status="posted", posted_by_user_id=maker,
                        evidence={},
                    )
                    db.add(transfer)
                    db.flush()
                    request = LoanRolloverReversalRequest(
                        company_id=company, transfer_id=transfer.id,
                        maker_user_id=maker, request_reference="AUTH-MAKER",
                        reason="Mistaken source installment rollover",
                    )
                    db.add(request)
                    db.flush()
                    decision = LoanRolloverReversalApproval(
                        company_id=company, transfer_id=transfer.id,
                        maker_user_id=maker, checker_user_id=checker,
                        approval_reference="AUTH-CHECKER",
                        decision="approved", reason="Reviewed original rollover records",
                        evidence={"maker_request_id": str(request.id)},
                    )
                    db.add(decision)
                    db.flush()
                    assert db.query(LoanRolloverReversalRequest).count() == 1
                    assert db.query(LoanRolloverReversalApproval).count() == 1
                    for statement in (
                        "UPDATE loan_rollover_reversal_requests SET reason='changed'",
                        "DELETE FROM loan_rollover_reversal_requests",
                        "UPDATE loan_rollover_reversal_approvals SET decision='rejected'",
                        "DELETE FROM loan_rollover_reversal_approvals",
                    ):
                        with pytest.raises(Exception, match="append-only"):
                            with db.begin_nested():
                                db.execute(text(statement))
                    for invalid_decision in ("unverified", "approved"):
                        with pytest.raises(IntegrityError):
                            with db.begin_nested():
                                db.add(LoanRolloverReversalApproval(
                                    company_id=company, transfer_id=transfer.id,
                                    maker_user_id=maker,
                                    checker_user_id=maker if invalid_decision == "approved" else checker,
                                    approval_reference="INVALID-" + invalid_decision,
                                    decision=invalid_decision, reason="invalid decision test",
                                    evidence={},
                                ))
                                db.flush()
                    assert db.query(LoanRolloverReversalRequest).count() == 1
                    assert db.query(LoanRolloverReversalApproval).count() == 1
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
