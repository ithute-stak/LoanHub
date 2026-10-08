from __future__ import annotations

from datetime import date
from pathlib import Path

from services.cdas_operations_kpis import _month_start, _next_month


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "apps" / "backend" / "services" / "cdas_operations_kpis.py"
ROUTER = ROOT / "apps" / "backend" / "routers" / "cdas_api.py"
PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas" / "manage" / "page.tsx"


def test_month_helpers_cross_year_boundary() -> None:
    assert _month_start(date(2026, 10, 8)) == date(2026, 10, 1)
    assert _next_month(date(2026, 12, 20)) == date(2027, 1, 1)


def test_kpis_are_current_architecture_only() -> None:
    source = SERVICE.read_text(encoding="utf-8")

    assert "CdasOfficialMandateState" in source
    assert "CDASDeductionMandate" in source
    assert "CDASRemittanceBatch" in source
    assert "latest_roster_snapshot" in source
    assert "CdasBookingOpportunity" not in source
    assert "CDAS_DAILY_INTELLIGENCE" not in source


def test_kpis_include_reconciliation_projection_and_remittance() -> None:
    source = SERVICE.read_text(encoding="utf-8")

    assert '"requires_reconciliation_count"' in source
    assert '"requires_reconciliation_monthly_amount"' in source
    assert '"projected_next_month"' in source
    assert '"latest_remittance"' in source
    assert '"exception_count"' in source
    assert '"monthly_active_deductions"' in source


def test_kpi_endpoint_is_tenant_and_branch_scoped() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/operations-kpis")' in source
    assert "_require_lending_user(context)" in source
    assert "company_id=context.company_id" in source
    assert "branch_id=context.branch_id" in source


def test_management_workspace_shows_operational_scorecard() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert 'api.get<OperationsKpis>("/cdas/operations-kpis")' in source
    assert "CDAS operational scorecard" in source
    assert "Active monthly deductions" in source
    assert "Pending lifecycle" in source
    assert "Reconciliation exposure" in source
    assert "Projected next month" in source
    assert "Latest remittance" in source
