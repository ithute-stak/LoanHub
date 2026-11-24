"""Real PostgreSQL proof of narrowly granted, privileged source row locks.

A definer-owned, scoped lock function is a *candidate* alternative to broad
UPDATE grants to the regular PDF issuance session. This uses a disposable
schema, role and data, never the live LoanHub schema. The actual application
function is not deployed by this test.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def test_narrow_definer_lock_cannot_be_used_for_another_tenant():
    url = os.getenv("LOANHUB_ISSUANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Real PostgreSQL test URL required")
    engine = create_engine(url, pool_size=2, max_overflow=0)
    suffix = uuid4().hex[:12]
    schema = "pdf_lock_guard_" + suffix
    role = "pdf_lock_caller_" + suffix
    tenant_a, tenant_b, loan_id, contract_id, file_id = [uuid4() for _ in range(5)]
    loan_b, contract_b, file_b = uuid4(), uuid4(), uuid4()
    try:
        with engine.begin() as setup:
            setup.execute(text(f'CREATE SCHEMA "{schema}"'))
            setup.execute(text(
                f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB '
                'NOCREATEROLE NOREPLICATION NOBYPASSRLS'
            ))
            setup.execute(text(
                f'CREATE TABLE "{schema}".loans (id uuid PRIMARY KEY, company_id uuid NOT NULL)'
            ))
            setup.execute(text(
                f'CREATE TABLE "{schema}".contracts '
                '(id uuid PRIMARY KEY, loan_id uuid NOT NULL, company_id uuid NOT NULL, '
                'pdf_file_id uuid NOT NULL, version int NOT NULL, status text NOT NULL)'
            ))
            setup.execute(text(
                f'CREATE TABLE "{schema}".files '
                '(id uuid PRIMARY KEY, company_id uuid NOT NULL, contract_id uuid NOT NULL)'
            ))
            setup.execute(text(
                f'INSERT INTO "{schema}".loans VALUES (:id,:tenant)'
            ), {"id": loan_id, "tenant": tenant_a})
            setup.execute(text(
                f'INSERT INTO "{schema}".contracts VALUES '
                '(:id,:loan,:tenant,:file,1,\'signed\')'
            ), {"id": contract_id, "loan": loan_id, "tenant": tenant_a, "file": file_id})
            setup.execute(text(
                f'INSERT INTO "{schema}".files VALUES (:id,:tenant,:contract)'
            ), {"id": file_id, "tenant": tenant_a, "contract": contract_id})
            # A second, otherwise valid tenant proves that spoofed custom
            # settings would unlock a real different-company source.
            setup.execute(text(
                f'INSERT INTO "{schema}".loans VALUES (:id,:tenant)'
            ), {"id": loan_b, "tenant": tenant_b})
            setup.execute(text(
                f"""INSERT INTO "{schema}".contracts
                    VALUES (:id,:loan,:tenant,:file,1,'signed')"""
            ), {"id": contract_b, "loan": loan_b, "tenant": tenant_b, "file": file_b})
            setup.execute(text(
                f'INSERT INTO "{schema}".files VALUES (:id,:tenant,:contract)'
            ), {"id": file_b, "tenant": tenant_b, "contract": contract_b})
            # SECURITY DEFINER's search_path is fixed; no dynamic SQL and
            # every row is explicitly scoped to the caller's claimed tenant.
            # This is a proof of privilege mechanics, NOT full authentication.
            setup.execute(text(f"""
                CREATE FUNCTION "{schema}".lock_signed_source(
                    p_tenant uuid, p_loan uuid, p_contract uuid, p_file uuid)
                RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
                SET search_path = pg_catalog
                AS $$
                DECLARE actual_tenant text;
                BEGIN
                    actual_tenant := current_setting('loanhub.company_id', true);
                    IF current_setting('loanhub.actor_scope', true) IS DISTINCT FROM 'tenant'
                       OR actual_tenant IS NULL OR actual_tenant = ''
                       OR actual_tenant::uuid IS DISTINCT FROM p_tenant THEN
                        RAISE EXCEPTION 'tenant verification required' USING ERRCODE='42501';
                    END IF;
                    PERFORM 1 FROM "{schema}".loans l
                      WHERE l.id=p_loan AND l.company_id=p_tenant
                      FOR SHARE NOWAIT;
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'loan not in tenant' USING ERRCODE='42501';
                    END IF;
                    PERFORM 1 FROM "{schema}".contracts c
                      WHERE c.id=p_contract AND c.loan_id=p_loan
                        AND c.company_id=p_tenant AND c.pdf_file_id=p_file
                        AND c.version=1 AND c.status='signed'
                      FOR SHARE NOWAIT;
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'contract not in tenant' USING ERRCODE='42501';
                    END IF;
                    PERFORM 1 FROM "{schema}".files f
                      WHERE f.id=p_file AND f.contract_id=p_contract
                        AND f.company_id=p_tenant
                      FOR SHARE NOWAIT;
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'file not in tenant' USING ERRCODE='42501';
                    END IF;
                    RETURN true;
                END $$;
            """))
            setup.execute(text(f'REVOKE ALL ON FUNCTION "{schema}".lock_signed_source(uuid,uuid,uuid,uuid) FROM PUBLIC'))
            setup.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            setup.execute(text(f'GRANT EXECUTE ON FUNCTION "{schema}".lock_signed_source(uuid,uuid,uuid,uuid) TO "{role}"'))
            setup.execute(text(f'GRANT SELECT ON "{schema}".loans, "{schema}".contracts, "{schema}".files TO "{role}"'))
        with engine.connect() as reader, engine.connect() as writer:
            rt, wt = reader.begin(), writer.begin()
            try:
                reader.execute(text(f'SET LOCAL ROLE "{role}"'))
                reader.execute(text("SELECT set_config('loanhub.actor_scope','tenant',true)"))
                reader.execute(text("SELECT set_config('loanhub.company_id',:tenant,true)"),
                               {"tenant": str(tenant_a)})
                assert reader.execute(text(f"""
                    SELECT "{schema}".lock_signed_source(
                        :tenant,:loan,:contract,:file)
                """), {"tenant": tenant_a, "loan": loan_id, "contract": contract_id,
                        "file": file_id}).scalar_one() is True
                # The ordinary role still cannot update the protected rows.
                savepoint = reader.begin_nested()
                try:
                    with pytest.raises(DBAPIError):
                        reader.execute(text(
                            f'UPDATE "{schema}".contracts SET status=\'draft\' WHERE id=:id'
                        ), {"id": contract_id})
                finally:
                    savepoint.rollback()
                writer.execute(text("SET LOCAL lock_timeout = '150ms'"))
                savepoint = writer.begin_nested()
                try:
                    with pytest.raises(DBAPIError):
                        writer.execute(text(
                            f'UPDATE "{schema}".contracts SET status=\'draft\' WHERE id=:id'
                        ), {"id": contract_id})
                finally:
                    savepoint.rollback()
                # Reject another tenant even when its ID is supplied explicitly.
                savepoint = reader.begin_nested()
                try:
                    with pytest.raises(DBAPIError):
                        reader.execute(text(f"""
                            SELECT "{schema}".lock_signed_source(:tenant,:loan,:contract,:file)
                        """), {"tenant": tenant_b, "loan": loan_id, "contract": contract_id,
                                "file": file_id})
                finally:
                    savepoint.rollback()
                # SECURITY FINDING: the restricted SQL caller controls custom
                # GUCs, so it can switch the claimed identity to company B.
                # This exact privileged lock prototype therefore cannot be
                # deployed as a tenant authentication or authorization gate.
                reader.execute(text(
                    "SELECT set_config('loanhub.company_id',:tenant,true)"
                ), {"tenant": str(tenant_b)})
                assert reader.execute(text(f"""
                    SELECT "{schema}".lock_signed_source(
                        :tenant,:loan,:contract,:file)
                """), {"tenant": tenant_b, "loan": loan_b, "contract": contract_b,
                        "file": file_b}).scalar_one() is True
                reader.execute(text("RESET ROLE"))
            finally:
                wt.rollback()
                rt.rollback()
    finally:
        try:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                conn.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        finally:
            engine.dispose()
