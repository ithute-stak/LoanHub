"""Real PostgreSQL enforcement of immutable approval revocation history."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


ROOT = Path(__file__).resolve().parents[1] / "alembic/versions"


def _upgrade(conn, filename):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(filename[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn))
    module.upgrade()


def _context(conn, tenant, scope="tenant"):
    conn.execute(text("SELECT set_config('loanhub.actor_scope', :v, true)"), {"v": scope})
    conn.execute(text("SELECT set_config('loanhub.company_id', :v, true)"), {"v": str(tenant)})


def _denied(conn, query):
    savepoint = conn.begin_nested()
    try:
        with pytest.raises(DBAPIError):
            conn.execute(text(query))
    finally:
        savepoint.rollback()


def test_revocation_ledger_is_tenant_read_only_on_real_postgresql():
    url = os.getenv("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Real PostgreSQL test URL required")
    engine = create_engine(url)
    suffix = uuid4().hex[:12]
    schema = "stamp_revoke_" + suffix
    role = "stamp_reader_" + suffix
    tenant_a, tenant_b, approver = uuid4(), uuid4(), uuid4()
    approval_a, approval_b = uuid4(), uuid4()
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(
                    f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB '
                    'NOCREATEROLE NOREPLICATION NOBYPASSRLS'
                ))
                conn.execute(text("SELECT set_config('search_path', :v, true)"),
                             {"v": schema})
                conn.execute(text("CREATE TABLE loan_companies (id uuid PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE users (id uuid PRIMARY KEY)"))
                conn.execute(text("INSERT INTO loan_companies(id) VALUES (:a),(:b)"),
                             {"a": tenant_a, "b": tenant_b})
                conn.execute(text("INSERT INTO users(id) VALUES (:u)"), {"u": approver})
                _upgrade(conn, "e7f8a9b0c124_document_stamp_approval_registry.py")
                _upgrade(conn, "f8a9b0c1d235_document_stamp_approval_revocations.py")
                for tenant, approval in ((tenant_a, approval_a), (tenant_b, approval_b)):
                    conn.execute(text(
                        "INSERT INTO document_stamp_approvals "
                        "(id, company_id, configuration_version, snapshot_sha256_hex, "
                        "approved_by_user_id, approved_at, status) "
                        "VALUES (:id,:tenant,1,:digest,:user,now(),'approved')"
                    ), {"id": approval, "tenant": tenant, "digest": "a" * 64,
                        "user": approver})
                conn.execute(text(
                    "INSERT INTO document_stamp_approval_revocations "
                    "(id, company_id, approval_id, revoked_by_user_id, reason) "
                    "VALUES (:id,:tenant,:approval,:user,:reason)"
                ), {"id": uuid4(), "tenant": tenant_b, "approval": approval_b,
                    "user": approver, "reason": "Discontinued and superseded stamp"})
                conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
                conn.execute(text(
                    f'GRANT SELECT ON "{schema}".document_stamp_approvals, '
                    f'"{schema}".document_stamp_approval_revocations TO "{role}"'
                ))
                conn.execute(text(f'SET LOCAL ROLE "{role}"'))
                assert conn.execute(text(
                    "SELECT count(*) FROM document_stamp_approval_revocations"
                )).scalar_one() == 0
                _context(conn, tenant_a)
                assert conn.execute(text(
                    "SELECT count(*) FROM document_stamp_approval_revocations"
                )).scalar_one() == 0
                _context(conn, tenant_b)
                assert conn.execute(text(
                    "SELECT count(*) FROM document_stamp_approval_revocations"
                )).scalar_one() == 1
                _denied(conn, "DELETE FROM document_stamp_approval_revocations")
                _denied(conn, "UPDATE document_stamp_approval_revocations SET reason='modified'")
                _denied(conn, "INSERT INTO document_stamp_approval_revocations "
                              "SELECT * FROM document_stamp_approval_revocations")
                _context(conn, tenant_b, scope="platform")
                assert conn.execute(text(
                    "SELECT count(*) FROM document_stamp_approval_revocations"
                )).scalar_one() == 0
                conn.execute(text("RESET ROLE"))
            finally:
                tx.rollback()
    finally:
        engine.dispose()
