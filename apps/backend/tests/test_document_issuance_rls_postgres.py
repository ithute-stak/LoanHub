"""Real PostgreSQL tests for the *actual* issuance Alembic RLS migration.

Uses a disposable schema and a real non-owner NOBYPASSRLS role. All schema,
roles and data are rolled back on test completion. Never touches live tables.
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
    "alembic/versions/c5d6e7f8a912_document_issuance_registry.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("document_issuance_pg_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _set_ctx(conn, *, company=None, user=None, role="company_admin", scope="tenant"):
    for key, value in (
        ("loanhub.actor_scope", scope),
        ("loanhub.company_id", str(company) if company else ""),
        ("loanhub.user_id", str(user) if user else ""),
        ("loanhub.role", role),
    ):
        conn.execute(text("SELECT set_config(:key, :value, true)"),
                     {"key": key, "value": value})


def _insert_issuance(conn, company, user, public_id, source):
    return conn.execute(text("""
        INSERT INTO document_issuances (
            id, company_id, public_id, idempotency_key, source_type,
            source_id, document_type, version, stamp_configuration_version,
            source_pdf_sha256, final_pdf_sha256, artifact_key, status,
            issued_by_user_id
        ) VALUES (
            :id, :company, :public_id, :public_id, 'workspace',
            :source, 'contract', 1, 1,
            :hash, :hash, :public_id, 'issued', :user
        )
        RETURNING id
    """), dict(id=uuid4(), company=company, public_id=public_id,
               source=source, hash="a" * 64, user=user)).scalar_one()


def _insert_event(conn, company, user, issuance):
    conn.execute(text("""
        INSERT INTO document_issuance_events (
            id, company_id, issuance_id, event_type, actor_user_id
        ) VALUES (:id, :company, :issuance, 'issued', :user)
    """), dict(id=uuid4(), company=company, issuance=issuance, user=user))


def _must_fail(conn, operation):
    savepoint = conn.begin_nested()
    try:
        with pytest.raises(DBAPIError):
            operation()
    finally:
        savepoint.rollback()


def test_document_issuance_rls_on_real_postgresql():
    url = os.environ.get("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set LOANHUB_ISSUANCE_TEST_POSTGRES_URL for real PostgreSQL security test")
    engine = create_engine(url)
    suffix = uuid4().hex[:12]
    schema = f"issuance_test_{suffix}"
    role = f"issuance_probe_{suffix}"
    tenant_a, tenant_b = uuid4(), uuid4()
    user_a, user_b = uuid4(), uuid4()
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS'))
                conn.execute(text(f"SELECT set_config('search_path', :path, true)"),
                             {"path": schema})
                conn.execute(text("CREATE TABLE loan_companies (id uuid PRIMARY KEY)"))
                conn.execute(text("CREATE TABLE users (id uuid PRIMARY KEY)"))
                conn.execute(text("INSERT INTO loan_companies (id) VALUES (:a), (:b)"),
                             dict(a=tenant_a, b=tenant_b))
                conn.execute(text("INSERT INTO users (id) VALUES (:a), (:b)"),
                             dict(a=user_a, b=user_b))

                module = _migration()
                module.op = Operations(MigrationContext.configure(conn))
                module.upgrade()
                policies = conn.execute(text("""
                    SELECT tablename, policyname FROM pg_policies
                    WHERE schemaname = :schema
                    ORDER BY tablename, policyname
                """), {"schema": schema}).all()
                assert len(policies) == 4

                # Seed as schema owner, whose role is intentionally distinct
                # from the restricted application role used below.
                a_id = _insert_issuance(conn, tenant_a, user_a, "document-a-1234567", "source-a")
                b_id = _insert_issuance(conn, tenant_b, user_b, "document-b-1234567", "source-b")
                _insert_event(conn, tenant_a, user_a, a_id)
                _insert_event(conn, tenant_b, user_b, b_id)

                conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
                conn.execute(text(
                    f'GRANT SELECT, INSERT ON "{schema}".document_issuances, '
                    f'"{schema}".document_issuance_events TO "{role}"'
                ))
                conn.execute(text(f'SET LOCAL ROLE "{role}"'))
                assert conn.execute(text("SELECT current_user")).scalar_one() == role
                assert conn.execute(text("""
                    SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user
                """)).scalar_one() is False

                # No auth context: both collections are hidden.
                assert conn.execute(text("SELECT count(*) FROM document_issuances")).scalar_one() == 0
                assert conn.execute(text("SELECT count(*) FROM document_issuance_events")).scalar_one() == 0

                _set_ctx(conn, company=tenant_a, user=user_a)
                assert conn.execute(text("SELECT public_id FROM document_issuances")).scalars().all() == ["document-a-1234567"]
                assert conn.execute(text("SELECT issuance_id FROM document_issuance_events")).scalars().all() == [a_id]
                _must_fail(conn, lambda: _insert_issuance(conn, tenant_b, user_a, "cross-tenant-12345", "cross"))
                _must_fail(conn, lambda: _insert_event(conn, tenant_a, user_a, b_id))
                _must_fail(conn, lambda: conn.execute(text(
                    "UPDATE document_issuances SET status='revoked' WHERE id=:id"
                ), {"id": a_id}))
                _must_fail(conn, lambda: conn.execute(text(
                    "DELETE FROM document_issuance_events WHERE issuance_id=:id"
                ), {"id": a_id}))

                _set_ctx(conn, company=tenant_a, user=user_a, role="loan_officer")
                _must_fail(conn, lambda: _insert_issuance(conn, tenant_a, user_a, "bad-role-1234567", "bad-role"))
                _set_ctx(conn, company=tenant_a, user=user_a, scope="platform")
                assert conn.execute(text("SELECT count(*) FROM document_issuances")).scalar_one() == 0
                conn.execute(text("RESET ROLE"))
            finally:
                tx.rollback()
    finally:
        engine.dispose()
