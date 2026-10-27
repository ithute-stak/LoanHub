"""PostgreSQL concurrency, idempotency, and rollback tests for rollover ledger invariants.

Temporary tables model the intended database transaction. These are database
constraint tests, NOT proof that the disabled loan-posting service is certified.
"""
import os
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def postgres_connection():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL integration DSN not configured")
    engine = create_engine(dsn)
    try:
        with engine.connect() as conn:
            outer = conn.begin()
            try:
                conn.execute(text("""
                    CREATE TEMP TABLE rollover_probe_loans (
                        loan_id text PRIMARY KEY,
                        parent_id text REFERENCES rollover_probe_loans(loan_id),
                        balance numeric(15,2) NOT NULL CHECK (balance >= 0),
                        UNIQUE (parent_id)
                    ) ON COMMIT DROP
                """))
                conn.execute(text("""
                    CREATE TEMP TABLE rollover_probe_transfers (
                        transfer_key text PRIMARY KEY,
                        parent_id text NOT NULL UNIQUE,
                        child_id text NOT NULL UNIQUE,
                        amount numeric(15,2) NOT NULL CHECK (amount > 0),
                        CHECK (parent_id <> child_id)
                    ) ON COMMIT DROP
                """))
                conn.execute(text(
                    "INSERT INTO rollover_probe_loans(loan_id,balance) VALUES ('parent',0.69)"
                ))
                yield conn
            finally:
                outer.rollback()
    finally:
        engine.dispose()


def test_approved_transfer_conserves_receivable_and_replay_is_rejected(postgres_connection):
    conn = postgres_connection
    conn.execute(text("UPDATE rollover_probe_loans SET balance=0 WHERE loan_id='parent'"))
    conn.execute(text(
        "INSERT INTO rollover_probe_loans(loan_id,parent_id,balance) VALUES ('child','parent',0.69)"
    ))
    conn.execute(text(
        "INSERT INTO rollover_probe_transfers(transfer_key,parent_id,child_id,amount) VALUES ('ref-1','parent','child',0.69)"
    ))
    total = conn.execute(text("SELECT sum(balance) FROM rollover_probe_loans")).scalar_one()
    assert total == Decimal("0.69")
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            conn.execute(text(
                "INSERT INTO rollover_probe_transfers(transfer_key,parent_id,child_id,amount) VALUES ('ref-1','parent','child',0.69)"
            ))
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            conn.execute(text(
                "INSERT INTO rollover_probe_loans(loan_id,parent_id,balance) VALUES ('child-2','parent',0.69)"
            ))
    assert conn.execute(text("SELECT sum(balance) FROM rollover_probe_loans")).scalar_one() == Decimal("0.69")


def test_transfer_failure_rolls_back_both_loan_balances(postgres_connection):
    conn = postgres_connection
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            conn.execute(text("UPDATE rollover_probe_loans SET balance=0 WHERE loan_id='parent'"))
            conn.execute(text(
                "INSERT INTO rollover_probe_loans(loan_id,parent_id,balance) VALUES ('child','missing',0.69)"
            ))
    assert conn.execute(text(
        "SELECT balance FROM rollover_probe_loans WHERE loan_id='parent'"
    )).scalar_one() == Decimal("0.69")
    assert conn.execute(text("SELECT count(*) FROM rollover_probe_loans")).scalar_one() == 1
