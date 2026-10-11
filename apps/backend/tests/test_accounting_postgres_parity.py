"""PostgreSQL query-execution test for advisory accounting isolation.

Uses temporary tables in a rollback-only transaction. This verifies scoped SQL
behavior; it does not claim database row-level security policy coverage.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from services import accounting_scoped_parity


def test_postgres_posted_scope_date_branch_read_only(monkeypatch):
    import os
    from urllib.parse import quote_plus

    url = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL accounting test DSN is not configured")
    engine = create_engine(url, pool_pre_ping=True)
    branch_a = UUID("00000000-0000-0000-0000-0000000000aa")
    branch_b = UUID("00000000-0000-0000-0000-0000000000bb")
    accounts = [UUID("00000000-0000-0000-0000-000000000011"), UUID("00000000-0000-0000-0000-000000000022")]
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            conn.execute(text("""CREATE TEMP TABLE journal_entries (
                id uuid PRIMARY KEY, scope_key varchar(80), status varchar(20),
                entry_date date, branch_id uuid
            ) ON COMMIT DROP"""))
            conn.execute(text("""CREATE TEMP TABLE journal_lines (
                id uuid PRIMARY KEY, journal_entry_id uuid, account_id uuid,
                debit numeric(18,2), credit numeric(18,2)
            ) ON COMMIT DROP"""))
            records = [
                ("company:A", "posted", date(2026, 1, 10), branch_a, Decimal("1.00")),
                ("company:B", "posted", date(2026, 1, 10), branch_a, Decimal("2.00")),
                ("company:A", "draft", date(2026, 1, 10), branch_a, Decimal("3.00")),
                ("company:A", "posted", date(2026, 2, 10), branch_a, Decimal("4.00")),
                ("company:A", "posted", date(2026, 1, 10), branch_b, Decimal("5.00")),
            ]
            for n, (scope, status, posting_date, branch, amount) in enumerate(records, 1):
                entry_id = UUID(int=n)
                conn.execute(text("""INSERT INTO journal_entries VALUES
                    (:id,:scope,:status,:entry_date,:branch)"""), {
                    "id": entry_id, "scope": scope, "status": status,
                    "entry_date": posting_date, "branch": branch,
                })
                for side, account in enumerate(accounts):
                    conn.execute(text("""INSERT INTO journal_lines VALUES
                        (:id,:journal_id,:account_id,:debit,:credit)"""), {
                        "id": UUID(int=100 + n * 2 + side), "journal_id": entry_id,
                        "account_id": account,
                        "debit": amount if side == 0 else Decimal("0"),
                        "credit": amount if side == 1 else Decimal("0"),
                    })
            captured = []
            def parity(rows):
                captured.extend(rows)
                return {"native_cpp_matched": False, "python_trial_balance": "100|100\\n"}
            monkeypatch.setattr(accounting_scoped_parity, "advisory_trial_balance", parity)
            with Session(bind=conn) as session:
                result = accounting_scoped_parity.scoped_trial_balance_parity(
                    session, scope_key="company:A", from_date=date(2026, 1, 1),
                    to_date=date(2026, 1, 31), branch_id=branch_a,
                )
                assert result["journal_line_count"] == 2
                assert sorted((d, c) for _, d, c in captured) == [
                    (Decimal("0.00"), Decimal("1.00")),
                    (Decimal("1.00"), Decimal("0.00")),
                ]
                assert result["authoritative"] is False
                assert not session.new and not session.dirty
        finally:
            transaction.rollback()
    engine.dispose()
