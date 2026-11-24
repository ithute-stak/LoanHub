"""Prove custom PostgreSQL tenant GUCs are not an authentication boundary.

This intentionally demonstrates a spoofing attack against a *disposable*
SECURITY DEFINER prototype. The production issuance service MUST NOT use
current_setting('loanhub.company_id') as its sole authorization evidence.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text


def test_database_client_can_spoof_tenant_setting_even_without_update_grants():
    url = os.getenv("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Real PostgreSQL test URL required")
    engine = create_engine(url)
    suffix = uuid4().hex[:12]
    schema = "spoof_probe_" + suffix
    role = "spoof_probe_reader_" + suffix
    company_a, company_b = uuid4(), uuid4()
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(
                    f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB '
                    'NOCREATEROLE NOREPLICATION NOBYPASSRLS'
                ))
                conn.execute(text(
                    f'CREATE TABLE "{schema}".documents '
                    '(id uuid PRIMARY KEY, company_id uuid NOT NULL)'
                ))
                conn.execute(text(
                    f'INSERT INTO "{schema}".documents VALUES (:a,:a),(:b,:b)'
                ), {"a": company_a, "b": company_b})
                # Insecure by design: proves that a definer function that
                # trusts a caller-controlled GUC grants another tenant's row.
                conn.execute(text(f"""
                    CREATE FUNCTION "{schema}".insecure_visible(p_id uuid)
                    RETURNS boolean
                    LANGUAGE sql SECURITY DEFINER
                    SET search_path = pg_catalog
                    AS $$
                      SELECT EXISTS (
                        SELECT 1 FROM "{schema}".documents d
                        WHERE d.id=p_id
                          AND d.company_id = NULLIF(
                            current_setting('loanhub.company_id', true), ''
                          )::uuid
                      )
                    $$;
                """))
                conn.execute(text(
                    f'REVOKE ALL ON FUNCTION "{schema}".insecure_visible(uuid) FROM PUBLIC'
                ))
                conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
                conn.execute(text(
                    f'GRANT EXECUTE ON FUNCTION "{schema}".insecure_visible(uuid) TO "{role}"'
                ))
                conn.execute(text(f'SET LOCAL ROLE "{role}"'))
                conn.execute(text(
                    "SELECT set_config('loanhub.company_id',:v,true)"
                ), {"v": str(company_a)})
                assert conn.execute(text(
                    f'SELECT "{schema}".insecure_visible(:id)'
                ), {"id": company_a}).scalar_one() is True
                assert conn.execute(text(
                    f'SELECT "{schema}".insecure_visible(:id)'
                ), {"id": company_b}).scalar_one() is False

                # Same restricted role can impersonate tenant B with SET.
                conn.execute(text(
                    "SELECT set_config('loanhub.company_id',:v,true)"
                ), {"v": str(company_b)})
                assert conn.execute(text(
                    f'SELECT "{schema}".insecure_visible(:id)'
                ), {"id": company_b}).scalar_one() is True
                conn.execute(text("RESET ROLE"))
            finally:
                tx.rollback()
    finally:
        engine.dispose()
