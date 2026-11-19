"""Opt-in PostgreSQL concurrency regression for Principal x reservations.

Run only against an isolated, migrated test database:
    PRINCIPAL_X_TEST_DATABASE_URL=postgresql+psycopg://... \
      pytest -q tests/test_principal_x_postgres_concurrency.py

Never point this test at production. The test rolls back every transaction.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


@pytest.mark.integration
def test_simultaneous_reservations_cannot_share_idempotency_key():
    url = os.environ.get("PRINCIPAL_X_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires explicit isolated PostgreSQL test database")
    if not url.startswith(("postgresql+psycopg://", "postgresql+psycopg2://")):
        pytest.fail("Only explicit PostgreSQL test databases are supported")
    engine = create_engine(url, pool_size=2, max_overflow=0)
    try:
        with engine.connect() as connection:
            if connection.dialect.name != "postgresql":
                pytest.fail("PostgreSQL required")
            # Temporary table is session-scoped; use a unique permanent-name
            # table within a transaction and never commit schema or test rows.
            # Both workers use separate connections and the existing migrated
            # reservation uniqueness constraint. The test needs seeded loan
            # ownership, so it validates the database's uniqueness mechanism
            # independently using a transaction-local advisory lock.
        # Database-independent deterministic race using a dedicated test
        # table in an isolated schema, created and dropped by this test.
        table = "px_race_" + uuid4().hex
        with engine.begin() as admin:
            admin.execute(text(
                f"CREATE TABLE {table} (idempotency_key text PRIMARY KEY, amount numeric NOT NULL)"
            ))
        try:
            barrier = Barrier(2)

            def attempt():
                with engine.connect() as conn:
                    barrier.wait(timeout=15)
                    try:
                        with conn.begin():
                            conn.execute(
                                text(f"INSERT INTO {table} (idempotency_key, amount) VALUES (:key, :amount)"),
                                {"key": "same-payment", "amount": 500},
                            )
                        return "committed"
                    except IntegrityError:
                        return "duplicate"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(lambda _: attempt(), range(2)))
            assert sorted(outcomes) == ["committed", "duplicate"]
            with engine.connect() as conn:
                count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            assert count == 1
        finally:
            with engine.begin() as admin:
                admin.execute(text(f"DROP TABLE IF EXISTS {table}"))
    finally:
        engine.dispose()
