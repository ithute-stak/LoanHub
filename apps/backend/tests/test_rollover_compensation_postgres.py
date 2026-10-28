"""PostgreSQL transactional compensation probes using isolated temporary tables.

These verify database failure atomicity and uniqueness but do not certify the
disabled production loan posting service.
"""
import os
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def conn():
    dsn=os.getenv("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL DSN not configured")
    engine=create_engine(dsn)
    try:
        with engine.connect() as connection:
            outer=connection.begin()
            try:
                connection.execute(text("""
                    CREATE TEMP TABLE compensation_probe_loans (
                      id text PRIMARY KEY, balance numeric(15,2) NOT NULL CHECK(balance>=0)
                    ) ON COMMIT DROP
                """))
                connection.execute(text("""
                    CREATE TEMP TABLE compensation_probe_records (
                      transfer_id text NOT NULL UNIQUE,
                      reference text NOT NULL UNIQUE,
                      amount numeric(15,2) NOT NULL CHECK(amount>0)
                    ) ON COMMIT DROP
                """))
                connection.execute(text("INSERT INTO compensation_probe_loans VALUES ('parent',0),('child',25.50)"))
                yield connection
            finally:
                outer.rollback()
    finally:
        engine.dispose()


def test_compensation_preserves_total_receivable(conn):
    conn.execute(text("UPDATE compensation_probe_loans SET balance=25.50 WHERE id='parent'"))
    conn.execute(text("UPDATE compensation_probe_loans SET balance=0 WHERE id='child'"))
    conn.execute(text("INSERT INTO compensation_probe_records VALUES ('transfer-1','reverse-1',25.50)"))
    assert conn.execute(text("SELECT sum(balance) FROM compensation_probe_loans")).scalar_one()==Decimal("25.50")


def test_duplicate_compensation_rolls_back_balance_changes(conn):
    conn.execute(text("INSERT INTO compensation_probe_records VALUES ('transfer-1','reverse-1',25.50)"))
    with pytest.raises(IntegrityError):
        with conn.begin_nested():
            conn.execute(text("UPDATE compensation_probe_loans SET balance=25.50 WHERE id='parent'"))
            conn.execute(text("UPDATE compensation_probe_loans SET balance=0 WHERE id='child'"))
            conn.execute(text("INSERT INTO compensation_probe_records VALUES ('transfer-1','reverse-2',25.50)"))
    assert conn.execute(text("SELECT balance FROM compensation_probe_loans WHERE id='parent'")).scalar_one()==Decimal("0")
    assert conn.execute(text("SELECT balance FROM compensation_probe_loans WHERE id='child'")).scalar_one()==Decimal("25.50")
