"""Real PostgreSQL RLS contract for the draft official stamp approval registry.

Runs in a disposable rolled-back schema with a genuine non-owner runtime role.
"""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


MIGRATION = (
    Path(__file__).resolve().parents[1] /
    "alembic/versions/e7f8a9b0c124_document_stamp_approval_registry.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("stamp_approval_registry_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _set_tenant(conn, tenant, *, scope="tenant"):
    conn.execute(text("SELECT set_config('loanhub.actor_scope', :value, true)"),
                 {"value": scope})
    conn.execute(text("SELECT set_config('loanhub.company_id', :value, true)"),
                 {"value": str(tenant) if tenant else ""})


def _must_fail(conn, operation):
    savepoint = conn.begin_nested()
    try:
        with pytest.raises(DBAPIError):
            operation()
    finally:
        savepoint.rollback()


def test_approval_registry_rls_on_real_postgresql():
    url = os.environ.get("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Real PostgreSQL CI configuration required")
    engine = create_engine(url)
    suffix = uuid4().hex[:12]
    schema = f"approval_test_{suffix}"
    role = f"approval_probe_{suffix}"
    tenant_a, tenant_b = uuid4(), uuid4()
    approver = uuid4()
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(
                    f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB '
                    'NOCREATEROLE NOREPLICATION NOBYPASSRLS'
                ))
                conn.execute(text("SELECT set_config('search_path', :path, true)"),
                             {"path": schema})
                conn.execute(text("CREATE TABLE loan_companies (id uuid PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE users (id uuid PRIMARY KEY)"))
                conn.execute(text("INSERT INTO loan_companies (id) VALUES (:a), (:b)"),
                             {"a": tenant_a, "b": tenant_b})
                conn.execute(text("INSERT INTO users (id) VALUES (:id)"),
                             {"id": approver})
                migration = _load_migration()
                migration.op = Operations(MigrationContext.configure(conn))
                migration.upgrade()
                policies = conn.execute(text("""
                    SELECT policyname, cmd FROM pg_policies
                    WHERE schemaname = :schema AND tablename='document_stamp_approvals'
                """), {"schema": schema}).all()
                assert policies == [("document_stamp_approvals_tenant_select", "SELECT")]

                for tenant, version in ((tenant_a, 1), (tenant_b, 1)):
                    conn.execute(text("""
                        INSERT INTO document_stamp_approvals
                        (id, company_id, configuration_version, snapshot_sha256_hex,
                         approved_by_user_id, approved_at, status)
                        VALUES (:id, :tenant, :version, :digest, :approver,
                                now(), 'approved')
                    """), {"id": uuid4(), "tenant": tenant, "version": version,
                           "digest": "a" * 64, "approver": approver})

                conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
                conn.execute(text(
                    f'GRANT SELECT ON "{schema}".document_stamp_approvals TO "{role}"'
                ))
                conn.execute(text(f'SET LOCAL ROLE "{role}"'))
                assert conn.execute(text("""
                    SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname=current_user
                """)).scalar_one() is False
                assert conn.execute(text(
                    "SELECT count(*) FROM document_stamp_approvals"
                )).scalar_one() == 0
                _set_tenant(conn, tenant_a)
                assert conn.execute(text(
                    "SELECT company_id FROM document_stamp_approvals"
                )).scalars().all() == [tenant_a]
                _must_fail(conn, lambda: conn.execute(text(
                    "UPDATE document_stamp_approvals SET status='approved'"
                )))
                _must_fail(conn, lambda: conn.execute(text(
                    "DELETE FROM document_stamp_approvals"
                )))
                _must_fail(conn, lambda: conn.execute(text("""
                    INSERT INTO document_stamp_approvals
                    (id, company_id, configuration_version, snapshot_sha256_hex,
                     approved_by_user_id, approved_at, status)
                    VALUES (:id, :tenant, 2, :digest, :approver, now(), 'approved')
                """), {"id": uuid4(), "tenant": tenant_a,
                       "digest": "b" * 64, "approver": approver}))
                _set_tenant(conn, tenant_a, scope="platform")
                assert conn.execute(text(
                    "SELECT count(*) FROM document_stamp_approvals"
                )).scalar_one() == 0
                conn.execute(text("RESET ROLE"))
            finally:
                tx.rollback()
    finally:
        engine.dispose()
