"""Alembic-to-head smoke test on a disposable PostgreSQL database.

This is a schema certification gate only, not authorization to activate rollover.
No production or persistent database may be supplied here.
"""
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = (
    "client_company_loan",
    "repayment_installments",
    "loan_rollover_transfers",
    "audit_logs",
)


def test_full_migrations_provide_rollover_financial_schema():
    source = os.getenv("LOANHUB_MIGRATION_CERTIFICATION_POSTGRES_URL")
    if not source:
        pytest.skip("Dedicated disposable-database certification URL not configured")
    if os.getenv("CI") != "true":
        pytest.skip("Migration certification is restricted to isolated CI")

    url = make_url(source)
    assert url.get_backend_name() == "postgresql", "PostgreSQL is required"
    assert url.database == "loan_db", "Only the dedicated CI seed database is permitted"
    assert url.host in ("127.0.0.1", "localhost"), "Never run against remote databases"

    name = "loanhub_rollover_cert_" + uuid4().hex[:16]
    admin_url = url.set(database="postgres")
    test_url = url.set(database=name)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    created = False
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True

        env = os.environ.copy()
        env["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
        env["DB_NAME"] = name
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND, env=env, check=True, timeout=600,
        )
        cfg = Config(str(BACKEND / "alembic.ini"))
        expected_heads = set(ScriptDirectory.from_config(cfg).get_heads())
        assert len(expected_heads) == 1, "Migration history must have exactly one head"

        engine = create_engine(test_url)
        try:
            with engine.connect() as conn:
                actual_heads = set(conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalars())
                assert actual_heads == expected_heads
                inspector = inspect(conn)
                for table in EXPECTED_TABLES:
                    assert inspector.has_table(table), f"Missing migrated table: {table}"
                for table in ("client_company_loan", "repayment_installments", "loan_rollover_transfers"):
                    assert inspector.get_foreign_keys(table), f"Missing migrated foreign keys: {table}"
                child_columns = {c["name"] for c in inspector.get_columns("client_company_loan")}
                assert {"id", "company_id", "parent_loan_id", "folio_number", "balance"} <= child_columns
                transfer_columns = {c["name"] for c in inspector.get_columns("loan_rollover_transfers")}
                assert {"parent_loan_id", "child_loan_id", "transfer_amount",
                        "principal_component", "interest_component"} <= transfer_columns
        finally:
            engine.dispose()
    finally:
        if created:
            with admin.connect() as conn:
                conn.execute(text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database AND pid <> pg_backend_pid()"
                ), {"database": name})
                conn.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()
