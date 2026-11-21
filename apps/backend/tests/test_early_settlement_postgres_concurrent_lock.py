"""Two-connection PostgreSQL row-lock probe for settlement reversal.

Uses a uniquely named disposable table in the CI-only database. This verifies
database lock contention and status recheck semantics, NOT service integration.
Do not set LOANHUB_TEST_POSTGRES_URL to production or a shared database.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def test_two_connections_serialize_reversal_status_recheck():
    url = os.getenv("LOANHUB_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL URL is not configured")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        pytest.fail("PostgreSQL URL required")

    # A random identifier prevents collisions between CI runs; never touch
    # LoanHub application tables. The identifier is generated, not user input.
    table = "settlement_lock_probe_" + uuid4().hex
    engine = create_engine(url, pool_size=2, max_overflow=0, pool_pre_ping=True)
    try:
        with engine.begin() as setup:
            setup.execute(text(
                f"CREATE TABLE {table} (id integer PRIMARY KEY, status text NOT NULL)"
            ))
            setup.execute(text(
                f"INSERT INTO {table} (id, status) VALUES (1, 'settled')"
            ))
        try:
            with engine.connect() as first, engine.connect() as second:
                # First reversal obtains the quote row lock.
                assert first.execute(text(
                    f"SELECT status FROM {table} WHERE id = 1 FOR UPDATE"
                )).scalar_one() == "settled"

                # A competing reversal cannot acquire the same row lock.
                with pytest.raises(OperationalError):
                    second.execute(text(
                        f"SELECT status FROM {table} WHERE id = 1 FOR UPDATE NOWAIT"
                    )).scalar_one()
                second.rollback()

                # Commit the first reversal and release its lock.
                first.execute(text(
                    f"UPDATE {table} SET status = 'reversed' WHERE id = 1"
                ))
                first.commit()

                # The second reversal now locks and sees the new status;
                # it must not restore the same snapshot a second time.
                assert second.execute(text(
                    f"SELECT status FROM {table} WHERE id = 1 FOR UPDATE"
                )).scalar_one() == "reversed"
                second.rollback()
        finally:
            with engine.begin() as cleanup:
                cleanup.execute(text(f"DROP TABLE IF EXISTS {table}"))
    finally:
        engine.dispose()
