"""Restricted-role PostgreSQL RLS probe for accounting journal isolation.

Temporary tables and policies are a proof of the enforcement mechanism.
They do NOT assert that production journal tables already have these policies.
"""
import os
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text


def test_accounting_rls_restricted_role_denies_cross_tenant_reads():
    url = os.environ.get("LOANHUB_ACCOUNTING_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PostgreSQL accounting test DSN not configured")
    engine = create_engine(url)
    tenant_a = UUID("00000000-0000-0000-0000-0000000000aa")
    tenant_b = UUID("00000000-0000-0000-0000-0000000000bb")
    with engine.connect() as connection:
        tx = connection.begin()
        try:
            # Role exists only for this transaction; rollback removes it.
            connection.execute(text(
                "CREATE ROLE loanhub_accounting_rls_probe "
                "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ))
            connection.execute(text("""
                CREATE TEMP TABLE accounting_rls_probe (
                    id integer PRIMARY KEY, company_id uuid NOT NULL, amount integer NOT NULL
                ) ON COMMIT DROP
            """))
            connection.execute(text("""
                INSERT INTO accounting_rls_probe (id, company_id, amount)
                VALUES (1, :tenant_a, 100), (2, :tenant_b, 200)
            """), {"tenant_a": str(tenant_a), "tenant_b": str(tenant_b)})
            connection.execute(text(
                "ALTER TABLE accounting_rls_probe ENABLE ROW LEVEL SECURITY"
            ))
            connection.execute(text(
                "ALTER TABLE accounting_rls_probe FORCE ROW LEVEL SECURITY"
            ))
            connection.execute(text("""
                CREATE POLICY tenant_accounting_read ON accounting_rls_probe
                FOR SELECT USING (
                    current_setting('loanhub.actor_scope', true) = 'tenant'
                    AND company_id = NULLIF(
                        current_setting('loanhub.company_id', true), ''
                    )::uuid
                )
            """))
            connection.execute(text(
                "GRANT SELECT ON accounting_rls_probe TO loanhub_accounting_rls_probe"
            ))
            connection.execute(text("SET LOCAL ROLE loanhub_accounting_rls_probe"))
            assert connection.execute(text("SELECT current_user")).scalar() == "loanhub_accounting_rls_probe"
            # Fail closed without valid tenant context, even without a WHERE clause.
            assert connection.execute(text(
                "SELECT count(*) FROM accounting_rls_probe"
            )).scalar() == 0
            connection.execute(text(
                "SELECT set_config('loanhub.actor_scope', 'tenant', true)"
            ))
            connection.execute(text(
                "SELECT set_config('loanhub.company_id', :company, true)"
            ), {"company": str(tenant_a)})
            rows = connection.execute(text(
                "SELECT id, amount FROM accounting_rls_probe ORDER BY id"
            )).all()
            assert rows == [(1, 100)]
            connection.execute(text(
                "SELECT set_config('loanhub.company_id', :company, true)"
            ), {"company": str(tenant_b)})
            assert connection.execute(text(
                "SELECT id, amount FROM accounting_rls_probe"
            )).all() == [(2, 200)]
            connection.execute(text("RESET ROLE"))
        finally:
            tx.rollback()
    engine.dispose()
