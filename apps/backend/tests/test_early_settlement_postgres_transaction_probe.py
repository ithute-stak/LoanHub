"""Opt-in PostgreSQL transactional probe for settlement-style money retention.

This test uses an isolated TEMP table, never application tables. It verifies
PostgreSQL cent precision, atomic rollback and committed state within a
single isolated connection. It is infrastructure groundwork, NOT a service
end-to-end integration test.

Set LOANHUB_TEST_POSTGRES_URL to a disposable PostgreSQL database URL to run.
Do not point this test at production or a shared database.
"""
import os
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def isolated_postgres_connection():
    url = os.getenv("LOANHUB_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set LOANHUB_TEST_POSTGRES_URL for isolated PostgreSQL tests")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        pytest.fail("LOANHUB_TEST_POSTGRES_URL must be a PostgreSQL connection URL")
    # A separate temporary table is scoped to this connection; the application
    # tables are never queried or mutated.
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "CREATE TEMP TABLE settlement_probe ("
                "id integer PRIMARY KEY, paid_amount numeric(15,2) NOT NULL, "
                "is_superseded boolean NOT NULL)"
            ))
            conn.commit()
            yield conn
    finally:
        engine.dispose()


@pytest.mark.parametrize("retained_cents", ["0.08", "0.40"])
def test_postgres_preserves_superseded_cents_and_rolls_back(isolated_postgres_connection, retained_cents):
    conn = isolated_postgres_connection
    original = Decimal(retained_cents)
    conn.execute(
        text("INSERT INTO settlement_probe (id, paid_amount, is_superseded) VALUES (1, :amount, false)"),
        {"amount": original},
    )
    conn.commit()

    conn.execute(text("UPDATE settlement_probe SET is_superseded = true WHERE id = 1"))
    conn.commit()
    retained = conn.execute(text(
        "SELECT paid_amount, is_superseded FROM settlement_probe WHERE id = 1"
    )).one()
    assert retained.paid_amount == original
    assert retained.is_superseded is True
    conn.rollback()

    conn.execute(text("UPDATE settlement_probe SET paid_amount = 0, is_superseded = false WHERE id = 1"))
    conn.rollback()
    restored = conn.execute(text(
        "SELECT paid_amount, is_superseded FROM settlement_probe WHERE id = 1"
    )).one()
    assert restored.paid_amount == original
    assert restored.is_superseded is True
    conn.rollback()
