"""Opt-in PostgreSQL race test for the loan-lock plus 2x-ceiling algorithm.

Uses isolated disposable test tables, NOT LoanHub's production payment tables.
This verifies the concurrency pattern; end-to-end LoanHub integration remains
a separate release blocker. Never run against a production database.

PRINCIPAL_X_TEST_DATABASE_URL=postgresql+psycopg://... \
  pytest -q tests/test_principal_x_postgres_ceiling_race.py
"""
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_two_distinct_payments_cannot_breach_two_times_principal():
    url = os.getenv("PRINCIPAL_X_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set an isolated PostgreSQL test database URL explicitly")
    if not url.startswith(("postgresql+psycopg://", "postgresql+psycopg2://")):
        pytest.fail("PostgreSQL test database required")
    engine = create_engine(url, pool_size=2, max_overflow=1)
    suffix = uuid4().hex
    loans = "px_test_loans_" + suffix
    payments = "px_test_payments_" + suffix
    try:
        with engine.begin() as conn:
            conn.execute(text(
                f"CREATE TABLE {loans} (id integer PRIMARY KEY, principal numeric(15,2) NOT NULL)"
            ))
            conn.execute(text(
                f"CREATE TABLE {payments} (idempotency_key text PRIMARY KEY, "
                "loan_id integer NOT NULL, amount numeric(15,2) NOT NULL)"
            ))
            conn.execute(text(f"INSERT INTO {loans} VALUES (1, 1000)"))
            conn.execute(text(
                f"INSERT INTO {payments} VALUES ('historical', 1, 1500)"
            ))
        barrier = Barrier(2)

        def attempt(key):
            barrier.wait(timeout=20)
            with engine.begin() as conn:
                # Serialize both different idempotency keys on the SAME loan.
                principal = Decimal(str(conn.execute(text(
                    f"SELECT principal FROM {loans} WHERE id=1 FOR UPDATE"
                )).scalar_one()))
                collected = Decimal(str(conn.execute(text(
                    f"SELECT COALESCE(SUM(amount), 0) FROM {payments} WHERE loan_id=1"
                )).scalar_one()))
                proposed = Decimal("400")
                if collected + proposed > principal * 2:
                    return "ceiling_rejected"
                conn.execute(text(
                    f"INSERT INTO {payments} (idempotency_key, loan_id, amount) "
                    "VALUES (:key, 1, :amount)"
                ), {"key": key, "amount": proposed})
                return "committed"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(attempt, ("payment-a", "payment-b")))
        assert sorted(outcomes) == ["ceiling_rejected", "committed"]
        with engine.connect() as conn:
            total = Decimal(str(conn.execute(text(
                f"SELECT SUM(amount) FROM {payments} WHERE loan_id=1"
            )).scalar_one()))
        assert total == Decimal("1900")
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {payments}"))
            conn.execute(text(f"DROP TABLE IF EXISTS {loans}"))
        engine.dispose()
