"""Inspect actual Alembic-migrated CDAS request table in disposable PostgreSQL.

Unlike a TEMP constraint probe, this test runs the full production migration
chain on a NEW isolated local CI database and inspects the resulting schema.
It does not contact CDAS or mutate any persistent application database.
"""
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]


def test_real_migrated_cdas_attempt_schema_has_fail_closed_guards():
    source = os.getenv("LOANHUB_MIGRATION_CERTIFICATION_POSTGRES_URL")
    if os.getenv("CI") != "true" or not source:
        pytest.skip("Only runs with an explicitly configured disposable CI PostgreSQL instance")
    url = make_url(source)
    assert url.get_backend_name() == "postgresql"
    assert url.database == "loan_db"
    assert url.host in ("127.0.0.1", "localhost")

    name = "loanhub_cdas_cert_" + uuid4().hex[:16]
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    created = False
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        target = url.set(database=name)
        env = os.environ.copy()
        env["DATABASE_URL"] = target.render_as_string(hide_password=False)
        env["DB_NAME"] = name
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND, env=env, check=True, timeout=600,
            stdout=subprocess.DEVNULL,
        )
        engine = create_engine(target)
        try:
            with engine.connect() as connection:
                inspector = inspect(connection)
                assert inspector.has_table("cdas_affordability_attempts")
                columns = {col["name"]: col for col in inspector.get_columns("cdas_affordability_attempts")}
                for required in (
                    "company_id", "borrower_id", "actor_user_id", "idempotency_key",
                    "request_fingerprint", "state", "assessment_record_id",
                ):
                    assert required in columns
                for required in ("company_id", "borrower_id", "idempotency_key",
                                 "request_fingerprint", "state"):
                    assert not columns[required]["nullable"]
                indexes = {
                    index["name"]: index
                    for index in inspector.get_indexes("cdas_affordability_attempts")
                }
                assert indexes["uq_cdas_aff_attempt_unresolved_fingerprint"]["unique"]
                predicate = str(indexes["uq_cdas_aff_attempt_unresolved_fingerprint"].get("dialect_options", {}).get("postgresql_where", ""))
                assert "reserved" in predicate and "unknown" in predicate
                uniques = {item["name"] for item in inspector.get_unique_constraints("cdas_affordability_attempts")}
                assert "uq_cdas_aff_attempt_company_key" in uniques
                checks = {item["name"] for item in inspector.get_check_constraints("cdas_affordability_attempts")}
                assert "ck_cdas_aff_attempt_state" in checks
                foreign_keys = {
                    tuple(key["constrained_columns"]): key["referred_table"]
                    for key in inspector.get_foreign_keys("cdas_affordability_attempts")
                }
                assert foreign_keys[("company_id",)] == "loan_companies"
                assert foreign_keys[("borrower_id",)] == "borrowers"
                cfg = Config(str(BACKEND / "alembic.ini"))
                heads = set(ScriptDirectory.from_config(cfg).get_heads())
                assert len(heads) == 1
                assert set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars()) == heads
        finally:
            engine.dispose()
    finally:
        if created:
            with admin.connect() as conn:
                conn.execute(text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ), {"name": name})
                conn.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()
