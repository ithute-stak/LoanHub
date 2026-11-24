"""PostgreSQL branch-day lock probe for staged financial controls.

Uses disposable tables and two real PostgreSQL transactions. Verifies the
same lock-then-check pattern as the treasury service. It is not a substitute
for production ORM/API integration, which remains a separate activation gate.
"""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def test_branch_cash_row_lock_prevents_simultaneous_overspend():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("Disposable PostgreSQL integration DSN not provided")
    engine = create_engine(dsn, pool_size=3, max_overflow=0)
    table = "branch_cash_lock_probe_" + uuid4().hex[:16]
    first_branch, other_branch = uuid4(), uuid4()
    barrier = Barrier(2)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE {table} (
                    branch_id uuid PRIMARY KEY,
                    opening numeric(15,2) NOT NULL,
                    receipts numeric(15,2) NOT NULL DEFAULT 0,
                    posted_out numeric(15,2) NOT NULL DEFAULT 0,
                    CHECK (posted_out >= 0)
                )
            """))
            conn.execute(text(f"""
                INSERT INTO {table} (branch_id, opening, receipts)
                VALUES (:branch, 100, 25), (:other, 10, 0)
            """), {"branch": first_branch, "other": other_branch})

        def payout(amount: Decimal) -> bool:
            barrier.wait(timeout=12)
            with Session(engine) as db:
                with db.begin():
                    row = db.execute(text(f"""
                        SELECT opening, receipts, posted_out FROM {table}
                        WHERE branch_id = :branch FOR UPDATE
                    """), {"branch": first_branch}).one()
                    available = row.opening + row.receipts - row.posted_out
                    if amount > available:
                        return False
                    db.execute(text(f"""
                        UPDATE {table} SET posted_out = posted_out + :amount
                        WHERE branch_id = :branch
                    """), {"branch": first_branch, "amount": amount})
                    return True

        with ThreadPoolExecutor(max_workers=2) as pool:
            approvals = [
                future.result(timeout=25)
                for future in (
                    pool.submit(payout, Decimal("80.00")),
                    pool.submit(payout, Decimal("80.00")),
                )
            ]
        assert sorted(approvals) == [False, True]
        with engine.connect() as conn:
            rows = conn.execute(text(f"""
                SELECT branch_id, opening, receipts, posted_out FROM {table}
                ORDER BY branch_id
            """)).all()
        ledger = {row.branch_id: row for row in rows}
        assert ledger[first_branch].posted_out == Decimal("80.00")
        assert ledger[first_branch].opening + ledger[first_branch].receipts - ledger[first_branch].posted_out == Decimal("45.00")
        assert ledger[other_branch].posted_out == Decimal("0.00")
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        finally:
            engine.dispose()


def test_branch_cash_closed_day_rejects_posting_after_lock():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("Disposable PostgreSQL integration DSN not provided")
    engine = create_engine(dsn, pool_size=2, max_overflow=0)
    table = "branch_cash_closed_probe_" + uuid4().hex[:16]
    branch = uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE {table} (
                    branch_id uuid PRIMARY KEY,
                    opening numeric(15,2) NOT NULL,
                    posted_out numeric(15,2) NOT NULL,
                    status text NOT NULL
                )
            """))
            conn.execute(text(f"""
                INSERT INTO {table} (branch_id, opening, posted_out, status)
                VALUES (:id, 300, 0, 'open')
            """), {"id": branch})

        with engine.connect() as close, engine.connect() as payout:
            close.execute(text(f"SELECT branch_id FROM {table} WHERE branch_id=:id FOR UPDATE"), {"id": branch})
            close.execute(text(f"UPDATE {table} SET status='closed' WHERE branch_id=:id"), {"id": branch})
            payout.execute(text("SET LOCAL lock_timeout = '250ms'"))
            from sqlalchemy.exc import OperationalError
            with pytest.raises(OperationalError):
                payout.execute(text(f"SELECT status FROM {table} WHERE branch_id=:id FOR UPDATE"), {"id": branch})
            payout.rollback()
            close.commit()
            with payout.begin():
                state = payout.execute(text(f"SELECT status FROM {table} WHERE branch_id=:id FOR UPDATE"), {"id": branch}).scalar_one()
                assert state == "closed"
            with engine.connect() as verify:
                assert verify.execute(text(f"SELECT posted_out FROM {table} WHERE branch_id=:id"), {"id": branch}).scalar_one() == Decimal("0.00")
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        finally:
            engine.dispose()
