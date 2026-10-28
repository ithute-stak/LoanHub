"""Run the actual rollover service entrypoints against PostgreSQL.

Certification of the current fail-closed contract: neither service may issue a
SQL write, even when given an open PostgreSQL transaction. This is deliberately
not certification of the disabled transfer/reversal execution paths.
"""
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from services.final_installment_rollover_posting import post_final_rollover
from services.rollover_compensation_posting import post_rollover_compensation


@pytest.mark.parametrize("operation", ["transfer", "compensation"])
def test_actual_posting_entrypoints_never_write_postgresql(operation):
    dsn = os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN is not configured")
    engine = create_engine(dsn)
    statements = []
    def capture(_conn, _cursor, statement, _params, _context, _executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                with Session(bind=conn) as db:
                    if operation == "transfer":
                        call = lambda: post_final_rollover(
                            db, company_id=uuid4(), parent_id=uuid4(),
                            installment_id=uuid4(), approved_amount=Decimal("60"),
                            due_date=date(2026, 12, 1), agreement_reference="TEST-AGREEMENT",
                            approval_reference="TEST-APPROVAL", actor_user_id=uuid4(),
                            actor_role="company_owner", as_of=date(2026, 10, 28),
                        )
                    else:
                        call = lambda: post_rollover_compensation(
                            db, company_id=uuid4(), transfer_id=uuid4(),
                            actor_user_id=uuid4(), independent_approver_id=uuid4(),
                            reference="TEST-REVERSAL", approval_reference="TEST-APPROVAL",
                            reason="Rollback-only service certification",
                        )
                    with pytest.raises(HTTPException) as exc:
                        call()
                    assert exc.value.status_code == 503
                    assert not db.new and not db.dirty and not db.deleted
                assert statements == [], "Disabled financial entrypoint executed SQL"
            finally:
                outer.rollback()
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        engine.dispose()
