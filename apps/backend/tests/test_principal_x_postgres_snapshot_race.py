"""Opt-in PostgreSQL tests for settlement-review snapshot isolation.

Disposable test tables only. Never point this suite at production.
PRINCIPAL_X_TEST_DATABASE_URL=postgresql+psycopg://... \\
    pytest -q tests/test_principal_x_postgres_snapshot_race.py

These tests exercise PostgreSQL concurrency mechanisms, not a certified
end-to-end settlement writer or third-party provider ledger.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def sandbox_tables():
    url = os.getenv("PRINCIPAL_X_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit isolated PostgreSQL test database is required")
    if not url.startswith(("postgresql+psycopg://", "postgresql+psycopg2://")):
        pytest.fail("Only an explicitly isolated PostgreSQL test database is supported")
    engine = create_engine(url, pool_size=3, max_overflow=0, pool_pre_ping=True)
    suffix = uuid4().hex
    loan_table, payment_table = "px_snapshot_loan_" + suffix, "px_snapshot_payment_" + suffix
    try:
        with engine.begin() as conn:
            conn.execute(text(
                f"CREATE TABLE {loan_table} (id integer PRIMARY KEY, version integer NOT NULL)"
            ))
            conn.execute(text(
                f"CREATE TABLE {payment_table} (id integer PRIMARY KEY, "
                "loan_id integer NOT NULL, amount numeric(15,2) NOT NULL)"
            ))
            conn.execute(text(f"INSERT INTO {loan_table} VALUES (1, 1)"))
            conn.execute(text(f"INSERT INTO {payment_table} VALUES (1, 1, 100.00)"))
        yield engine, loan_table, payment_table
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {payment_table}"))
                conn.execute(text(f"DROP TABLE IF EXISTS {loan_table}"))
        finally:
            engine.dispose()


@pytest.mark.integration
def test_writer_respecting_loan_lock_cannot_commit_during_review(sandbox_tables):
    engine, loans, payments = sandbox_tables
    review_locked = Event()
    allow_review_finish = Event()
    writer_started = Event()
    writer_done = Event()

    def reviewer():
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout = '10s'"))
            conn.execute(text(f"SELECT id FROM {loans} WHERE id=1 FOR UPDATE")).scalar_one()
            review_locked.set()
            before = conn.execute(text(
                f"SELECT count(*) FROM {payments} WHERE loan_id=1"
            )).scalar_one()
            assert allow_review_finish.wait(timeout=15)
            after = conn.execute(text(
                f"SELECT count(*) FROM {payments} WHERE loan_id=1"
            )).scalar_one()
            assert not writer_done.is_set()
            return before, after

    def writer():
        assert review_locked.wait(timeout=15)
        writer_started.set()
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout = '10s'"))
            # Contract: every financial writer must acquire the loan row lock.
            conn.execute(text(f"SELECT id FROM {loans} WHERE id=1 FOR UPDATE")).scalar_one()
            conn.execute(text(
                f"INSERT INTO {payments} (id, loan_id, amount) VALUES (2, 1, 50.00)"
            ))
        writer_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(reviewer)
        b = pool.submit(writer)
        assert review_locked.wait(timeout=15)
        assert writer_started.wait(timeout=15)
        assert not writer_done.is_set()
        allow_review_finish.set()
        assert a.result(timeout=20) == (1, 1)
        b.result(timeout=20)
    with engine.connect() as conn:
        assert conn.execute(text(
            f"SELECT count(*) FROM {payments} WHERE loan_id=1"
        )).scalar_one() == 2


@pytest.mark.integration
def test_uncooperative_writer_changes_read_committed_snapshot(sandbox_tables):
    engine, _, payments = sandbox_tables
    first_read_complete = Event()
    writer_done = Event()

    def reviewer():
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
                before = conn.execute(text(
                    f"SELECT count(*) FROM {payments} WHERE loan_id=1"
                )).scalar_one()
                first_read_complete.set()
                assert writer_done.wait(timeout=15)
                after = conn.execute(text(
                    f"SELECT count(*) FROM {payments} WHERE loan_id=1"
                )).scalar_one()
                return before, after

    def writer():
        assert first_read_complete.wait(timeout=15)
        with engine.begin() as conn:
            # Deliberately violates the application loan-lock convention.
            conn.execute(text(
                f"INSERT INTO {payments} (id, loan_id, amount) VALUES (2, 1, 50.00)"
            ))
        writer_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(reviewer)
        b = pool.submit(writer)
        assert a.result(timeout=20) == (1, 2)
        b.result(timeout=20)
