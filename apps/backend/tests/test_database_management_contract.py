"""Database-management contracts derived from the DBMS hardening phase."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
FRONTEND_ROOT = REPO / "apps" / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workload_indexes_match_critical_multi_column_queries() -> None:
    migration = _read(
        ROOT
        / "alembic/versions/d1f5h7j9k123_dbms_book_workload_integrity.py"
    )

    assert 'revision = "d1f5h7j9k123"' in migration
    assert 'down_revision = "c0e4g6h8j012"' in migration
    assert "ix_credit_bureau_enquiries_latest_experian_app" in migration
    assert "(company_id, application_id, borrower_id, completed_at DESC, requested_at DESC)" in migration
    assert "ix_platform_cb_tx_outstanding" in migration
    assert "status IN ('reserved', 'accrued', 'invoiced')" in migration
    assert "ix_platform_cb_tx_stale_reservations" in migration
    assert "ix_platform_cb_invoice_overdue" in migration
    assert "ix_cdas_mandates_company_loan" in migration
    assert "ix_credit_committee_conditions_gate" in migration
    assert "ix_credit_committee_cases_company_created" in migration


def test_financial_and_payroll_integrity_moves_into_database_constraints() -> None:
    migration = _read(
        ROOT
        / "alembic/versions/d1f5h7j9k123_dbms_book_workload_integrity.py"
    )

    assert "ck_platform_cb_subscription_financial_terms" in migration
    assert "billing_due_days BETWEEN 1 AND 90" in migration
    assert "ck_platform_cb_transaction_nonnegative_amounts" in migration
    assert "unit_price >= 0 AND amount >= 0" in migration
    assert "ck_platform_cb_invoice_financial_integrity" in migration
    assert "period_end >= period_start" in migration
    assert "ck_cdas_payroll_financial_integrity" in migration
    assert "maximum_deduction_percent <= 100" in migration
    assert "ck_cdas_mandate_financial_integrity" in migration
    assert "expected_installments >= 1" in migration
    assert "NOT VALID" in migration


def test_platform_database_management_is_read_only_and_owner_scoped() -> None:
    router = _read(ROOT / "routers/platform_database.py")
    service = _read(ROOT / "services/database_management_service.py")
    api_router = _read(ROOT / "api/v1/router.py")

    assert 'prefix="/platform-owner/database"' in router
    assert '@router.get("/health")' in router
    assert "require_platform_owner" in router
    assert "@router.post(" not in router
    assert "@router.put(" not in router
    assert "@router.patch(" not in router
    assert "@router.delete(" not in router
    assert "pg_stat_activity" in service
    assert "pg_stat_database" in service
    assert "pg_stat_user_tables" in service
    assert "pg_stat_user_indexes" in service
    assert "pg_constraint" in service
    assert "pg_stat_replication" in service
    assert "platform_database.router" in api_router


def test_database_management_ui_surfaces_workload_and_integrity_signals() -> None:
    page = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/superadmin/control/database-management/page.tsx"
    )
    controls = _read(
        FRONTEND_ROOT / "components/dashboard/superadmin-owner-control.tsx"
    )

    assert "PostgreSQL operating health" in page
    assert "Transaction & concurrency health" in page
    assert "Largest / busiest user tables" in page
    assert "Largest indexes" in page
    assert "Integrity validation queue" in page
    assert "Blocked PostgreSQL sessions detected." in page
    assert "Long-running transactions over 60 seconds detected." in page
    assert 'slug: "database-management"' in controls
    assert "Review index size and observed usage before adding or removing indexes." in controls
