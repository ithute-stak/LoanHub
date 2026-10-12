"""PostgreSQL accounting book summaries must exclude drafts, other tenants and branches."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from routers.accounting import _ledger_book_summary_data


def test_postgres_financial_books_summary_isolated_and_reconciled():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL CI connection not configured")
    engine = create_engine(dsn)
    a, b = UUID(int=11), UUID(int=12)
    branch_a, branch_b = UUID(int=21), UUID(int=22)
    with engine.connect() as conn:
        txn = conn.begin()
        try:
            conn.execute(text("""CREATE TEMP TABLE journal_entries (
                id uuid PRIMARY KEY, scope_key varchar(80), status varchar(20),
                entry_date date, branch_id uuid
            ) ON COMMIT DROP"""))
            conn.execute(text("""CREATE TEMP TABLE journal_lines (
                id uuid PRIMARY KEY, journal_entry_id uuid, account_id uuid,
                debit numeric(18,2), credit numeric(18,2)
            ) ON COMMIT DROP"""))
            cases = [
                ("company:A", "posted", date(2025, 12, 31), branch_a, "20.00"),
                ("company:A", "posted", date(2026, 1, 3), branch_a, "15.25"),
                ("company:B", "posted", date(2026, 1, 3), branch_a, "99.00"),
                ("company:A", "draft", date(2026, 1, 3), branch_a, "88.00"),
                ("company:A", "posted", date(2026, 1, 3), branch_b, "77.00"),
                ("company:A", "posted", date(2026, 2, 3), branch_a, "66.00"),
            ]
            for i, (scope, status, when, branch, amount) in enumerate(cases, 1):
                conn.execute(text("""INSERT INTO journal_entries VALUES
                    (:id,:scope,:status,:when,:branch)"""), dict(
                        id=UUID(int=i), scope=scope, status=status, when=when, branch=branch,
                ))
                for n, (account, debit, credit) in enumerate([
                    (a, amount, "0"), (b, "0", amount),
                ]):
                    conn.execute(text("""INSERT INTO journal_lines VALUES
                        (:id,:journal,:account,:debit,:credit)"""), dict(
                            id=UUID(int=100+i*2+n), journal=UUID(int=i),
                            account=account, debit=Decimal(debit), credit=Decimal(credit),
                    ))
            accounts = [
                SimpleNamespace(id=a, code="100", name="Cash", account_type="asset", normal_balance="debit"),
                SimpleNamespace(id=b, code="200", name="Liability", account_type="liability", normal_balance="credit"),
            ]
            with Session(bind=conn) as session:
                rows = _ledger_book_summary_data(
                    session, key="company:A", accounts=accounts,
                    from_date=date(2026, 1, 1), to_date=date(2026, 1, 31),
                    branch_id=branch_a,
                )
                assert len(rows) == 2
                assert rows[0]["opening_balance"] == rows[1]["opening_balance"] == Decimal("20.00")
                assert rows[0]["period_debit"] == rows[1]["period_credit"] == Decimal("15.25")
                assert rows[0]["closing_balance"] == rows[1]["closing_balance"] == Decimal("35.25")
                assert rows[0]["period_credit"] == rows[1]["period_debit"] == Decimal("0.00")
                assert not session.new and not session.dirty
        finally:
            txn.rollback()
    engine.dispose()
