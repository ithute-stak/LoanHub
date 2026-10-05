"""Pilot PostgreSQL row-level tenant isolation on internal company operations.

Revision ID: e2g6i8k0l234
Revises: d1f5h7j9k123
Create Date: 2026-10-05

This migration depends operationally on the restricted runtime role introduced
by the DBMS least-privilege work and on verified per-transaction tenant context.
The migration owner remains able to administer schema; normal runtime sessions
are constrained by these policies.
"""

from alembic import op


revision = "e2g6i8k0l234"
down_revision = "d1f5h7j9k123"
branch_labels = None
depends_on = None


_TABLES = (
    "crm_relationship_cases",
    "collateral_assets",
    "legal_recovery_matters",
)

_PLATFORM_READ_ROLES = (
    "superadmin",
    "platform_admin",
    "platform_finance",
    "platform_support",
    "platform_auditor",
    "platform_operations",
    "platform_compliance",
)

_PLATFORM_WRITE_ROLES = (
    "superadmin",
    "platform_admin",
    "platform_operations",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _tenant_predicate() -> str:
    return """
    current_setting('loanhub.actor_scope', true) = 'tenant'
    AND company_id = NULLIF(
        current_setting('loanhub.company_id', true),
        ''
    )::uuid
    """


def _platform_predicate(roles: tuple[str, ...]) -> str:
    return f"""
    current_setting('loanhub.actor_scope', true) = 'platform'
    AND current_setting('loanhub.role', true) IN ({_quoted(roles)})
    """


def upgrade() -> None:
    tenant = _tenant_predicate()
    platform_read = _platform_predicate(_PLATFORM_READ_ROLES)
    platform_write = _platform_predicate(_PLATFORM_WRITE_ROLES)

    for table in _TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')

        op.execute(
            f"""
            CREATE POLICY loanhub_tenant_select
            ON "{table}"
            FOR SELECT
            USING (({tenant}) OR ({platform_read}))
            """
        )
        op.execute(
            f"""
            CREATE POLICY loanhub_tenant_insert
            ON "{table}"
            FOR INSERT
            WITH CHECK (({tenant}) OR ({platform_write}))
            """
        )
        op.execute(
            f"""
            CREATE POLICY loanhub_tenant_update
            ON "{table}"
            FOR UPDATE
            USING (({tenant}) OR ({platform_write}))
            WITH CHECK (({tenant}) OR ({platform_write}))
            """
        )
        op.execute(
            f"""
            CREATE POLICY loanhub_tenant_delete
            ON "{table}"
            FOR DELETE
            USING (({tenant}) OR ({platform_write}))
            """
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f'DROP POLICY IF EXISTS loanhub_tenant_delete ON "{table}"')
        op.execute(f'DROP POLICY IF EXISTS loanhub_tenant_update ON "{table}"')
        op.execute(f'DROP POLICY IF EXISTS loanhub_tenant_insert ON "{table}"')
        op.execute(f'DROP POLICY IF EXISTS loanhub_tenant_select ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
