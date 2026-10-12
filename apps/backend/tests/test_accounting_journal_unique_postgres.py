"""Verify PostgreSQL journal uniqueness contracts in rollback-only temporary tables."""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


def test_postgres_journal_reference_and_number_uniqueness():
    dsn = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("PostgreSQL test connection not configured")
    engine = create_engine(dsn)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TEMP TABLE accounting_unique_probe (
              id integer PRIMARY KEY,
              scope_key varchar(80) NOT NULL,
              entry_number varchar(60) NOT NULL,
              reference_type varchar(80),
              reference_id varchar(120),
              UNIQUE (scope_key, entry_number),
              UNIQUE (scope_key, reference_type, reference_id)
            ) ON COMMIT DROP
        """))
        def add(identifier, scope, number, reference):
            conn.execute(text("""
                INSERT INTO accounting_unique_probe
                  (id, scope_key, entry_number, reference_type, reference_id)
                VALUES (:id, :scope, :number, 'payment_transaction', :reference)
            """), dict(id=identifier, scope=scope, number=number, reference=reference))
        add(1, "company:A", "JRN-001", "payment-123")
        # Savepoints let the outer transaction continue after uniqueness errors.
        with pytest.raises(IntegrityError), conn.begin_nested():
            add(2, "company:A", "JRN-002", "payment-123")
        with pytest.raises(IntegrityError), conn.begin_nested():
            add(3, "company:A", "JRN-001", "payment-456")
        add(4, "company:B", "JRN-001", "payment-123")
        assert conn.execute(text("SELECT count(*) FROM accounting_unique_probe")).scalar() == 2
    engine.dispose()
