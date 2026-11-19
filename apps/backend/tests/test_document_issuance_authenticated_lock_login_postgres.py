"""Real PostgreSQL login-bound privilege proof for document source locking.

This proves one possible authentication primitive: session_user is established
by actual database login, and a definer function looks up tenant authorization
in an owner-controlled mapping. Caller-controlled custom settings are ignored.
This is isolated test scaffolding, NOT a LoanHub production role model.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def test_locked_source_tenant_is_bound_to_authenticated_database_login():
    url = os.getenv("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Real PostgreSQL test URL required")

    owner_engine = create_engine(url)
    suffix = uuid4().hex[:10]
    schema = "issuer_login_" + suffix
    login = "issuer_limited_" + suffix
    password = uuid4().hex + uuid4().hex
    tenant_a, tenant_b, loan_a, loan_b = [uuid4() for _ in range(4)]
    login_engine = None
    try:
        # DDL is committed before connecting as the actual restricted login.
        with owner_engine.begin() as owner:
            owner.execute(text(f'CREATE SCHEMA "{schema}"'))
            owner.execute(text(
                f"CREATE ROLE \"{login}\" LOGIN PASSWORD '{password}' "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ))
            owner.execute(text(
                f'CREATE TABLE "{schema}".trusted_login_tenants '
                '(role_name text PRIMARY KEY, company_id uuid NOT NULL)'
            ))
            owner.execute(text(
                f'CREATE TABLE "{schema}".loan_sources '
                '(id uuid PRIMARY KEY, company_id uuid NOT NULL, version int NOT NULL)'
            ))
            owner.execute(text(
                f'INSERT INTO "{schema}".trusted_login_tenants VALUES (:name,:company)'
            ), {"name": login, "company": tenant_a})
            owner.execute(text(
                f'INSERT INTO "{schema}".loan_sources VALUES (:id,:company,1),(:other,:b,1)'
            ), {"id": loan_a, "company": tenant_a,
                "other": loan_b, "b": tenant_b})
            owner.execute(text(f"""
                CREATE FUNCTION "{schema}".lock_authorized_loan(
                    p_company uuid, p_loan uuid)
                RETURNS boolean
                LANGUAGE plpgsql SECURITY DEFINER
                SET search_path = pg_catalog
                AS $$
                DECLARE allowed_company uuid;
                BEGIN
                    SELECT mapping.company_id INTO allowed_company
                    FROM "{schema}".trusted_login_tenants mapping
                    WHERE mapping.role_name = session_user;
                    IF allowed_company IS NULL
                       OR allowed_company IS DISTINCT FROM p_company THEN
                        RAISE EXCEPTION 'authenticated login not authorized for tenant'
                            USING ERRCODE = '42501';
                    END IF;
                    PERFORM 1 FROM "{schema}".loan_sources l
                    WHERE l.company_id = allowed_company AND l.id = p_loan
                    FOR SHARE NOWAIT;
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'loan source not authorized'
                            USING ERRCODE = '42501';
                    END IF;
                    RETURN true;
                END $$;
            """))
            owner.execute(text(
                f'REVOKE ALL ON FUNCTION "{schema}".lock_authorized_loan(uuid,uuid) FROM PUBLIC'
            ))
            owner.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{login}"'))
            owner.execute(text(
                f'GRANT EXECUTE ON FUNCTION "{schema}".lock_authorized_loan(uuid,uuid) TO "{login}"'
            ))
            # Login receives NO SELECT/UPDATE on the protected loan or mapping table.

        login_url = owner_engine.url.set(username=login, password=password)
        login_engine = create_engine(login_url)
        with login_engine.connect() as caller:
            tx = caller.begin()
            try:
                assert caller.execute(text("SELECT session_user")).scalar_one() == login
                assert caller.execute(text(
                    "SELECT rolbypassrls OR rolsuper "
                    "FROM pg_roles WHERE rolname=session_user"
                )).scalar_one() is False

                # An attempted impersonation changes both usual GUC values.
                caller.execute(text(
                    "SELECT set_config('loanhub.actor_scope','tenant',true)"
                ))
                caller.execute(text(
                    "SELECT set_config('loanhub.company_id',:company,true)"
                ), {"company": str(tenant_b)})
                savepoint = caller.begin_nested()
                try:
                    with pytest.raises(DBAPIError) as denied:
                        caller.execute(text(f"""
                            SELECT "{schema}".lock_authorized_loan(:company,:loan)
                        """), {"company": tenant_b, "loan": loan_b}).one()
                    assert (getattr(denied.value.orig, "pgcode", None)
                            or getattr(denied.value.orig, "sqlstate", None)) == "42501"
                finally:
                    savepoint.rollback()

                # Legitimate authenticated database login works even if the
                # untrusted GUC incorrectly claims tenant B.
                assert caller.execute(text(f"""
                    SELECT "{schema}".lock_authorized_loan(:company,:loan)
                """), {"company": tenant_a, "loan": loan_a}).scalar_one() is True

                # No table SELECT or direct UPDATE, even with approved login.
                for operation in (
                    f'SELECT id FROM "{schema}".trusted_login_tenants',
                    f'UPDATE "{schema}".loan_sources SET version=2',
                ):
                    savepoint = caller.begin_nested()
                    try:
                        with pytest.raises(DBAPIError):
                            caller.execute(text(operation))
                    finally:
                        savepoint.rollback()
                # The caller cannot grant itself an alternate database identity.
                savepoint = caller.begin_nested()
                try:
                    with pytest.raises(DBAPIError):
                        caller.execute(text("SET SESSION AUTHORIZATION postgres"))
                finally:
                    savepoint.rollback()
            finally:
                tx.rollback()
    finally:
        if login_engine is not None:
            login_engine.dispose()
        try:
            with owner_engine.begin() as owner:
                owner.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                owner.execute(text(f'DROP ROLE IF EXISTS "{login}"'))
        finally:
            owner_engine.dispose()
