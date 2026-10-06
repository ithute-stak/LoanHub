from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/e2g6i8k0l234_rls_pilot_tenant_operations.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("rls_pilot_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rls_pilot_targets_internal_company_owned_tables() -> None:
    migration = _load_migration()

    assert migration._TABLES == (
        "crm_relationship_cases",
        "collateral_assets",
        "legal_recovery_matters",
        "customer_complaint_cases",
        "company_operation_events",
        "procurement_vendors",
        "procurement_requests",
        "company_budget_plans",
        "company_budget_lines",
        "internal_audit_engagements",
        "internal_audit_findings",
    )


def test_tenant_predicate_is_fail_closed_and_company_scoped() -> None:
    migration = _load_migration()
    predicate = migration._tenant_predicate()

    assert "loanhub.actor_scope" in predicate
    assert "= 'tenant'" in predicate
    assert "company_id =" in predicate
    assert "loanhub.company_id" in predicate
    assert "NULLIF(" in predicate
    assert "::uuid" in predicate


def test_borrower_scope_is_not_permitted_by_pilot_policies() -> None:
    migration = _load_migration()

    assert "borrower" not in migration._PLATFORM_READ_ROLES
    assert "borrower" not in migration._PLATFORM_WRITE_ROLES


def test_platform_read_and_write_permissions_are_not_equivalent() -> None:
    migration = _load_migration()

    assert "platform_auditor" in migration._PLATFORM_READ_ROLES
    assert "platform_auditor" not in migration._PLATFORM_WRITE_ROLES
    assert "platform_support" in migration._PLATFORM_READ_ROLES
    assert "platform_support" not in migration._PLATFORM_WRITE_ROLES
    assert set(migration._PLATFORM_WRITE_ROLES) < set(migration._PLATFORM_READ_ROLES)


def test_rls_pilot_does_not_force_schema_owner_through_runtime_policy() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" not in source
    assert "DISABLE ROW LEVEL SECURITY" in source
