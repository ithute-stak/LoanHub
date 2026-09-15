from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_management_dashboard_route_api_navigation_and_registry_are_wired() -> None:
    api = _read(FRONTEND / "api" / "cdasBooking.ts")
    layout = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx")
    page = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "management-dashboard" / "page.tsx")
    router = _read(BACKEND / "routers" / "cdas_management_dashboard.py")
    registry = _read(BACKEND / "api" / "v1" / "router.py")

    assert '"/cdas-booking/management-dashboard"' in api
    assert 'href="/company/cdas-booking/management-dashboard"' in layout
    assert "Management Dashboard" in layout
    assert "CdasManagementDashboardView" in page
    assert '@router.get("/management-dashboard")' in router
    assert "_require_company_member(context)" in router
    assert "cdas_management_dashboard" in registry
    assert "cdas_management_dashboard.router" in registry


def test_management_dashboard_queries_are_company_scoped_and_read_only() -> None:
    router = _read(BACKEND / "routers" / "cdas_management_dashboard.py")

    for model in (
        "CdasBookingOpportunity",
        "CdasAnalysisRecord",
        "CdasOpportunityContact",
        "CdasBookingFailure",
    ):
        assert f"{model}.company_id == context.company_id" in router

    assert "db.add(" not in router
    assert "db.delete(" not in router
    assert "db.commit(" not in router
    assert "build_booking_calendar" in router
    assert "build_booking_priority_queue" in router
    assert "build_opportunity_pipeline" in router
    assert "build_follow_up_workspace" in router
    assert "build_failure_workspace" in router
    assert "build_data_quality_centre" in router
    assert "build_duplicate_detection" in router
    assert "build_change_detection" in router
    assert "build_cdas_forecast" in router
    assert "build_management_dashboard" in router


def test_management_dashboard_ui_covers_operational_management_signals() -> None:
    component = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "CdasManagementDashboard.tsx"
    )

    for phrase in (
        "CDAS Management Dashboard",
        "Operations pulse",
        "Workflow attention",
        "Pipeline distribution",
        "Failure reasons",
        "Data quality and review",
        "Known booking-window forecast",
        "12-month outlook",
        "Top employers in forecast",
        "Top competitor agencies in forecast",
    ):
        assert phrase in component

    assert "does not determine borrower approval, eligibility, loan amount, pricing, disbursement or revenue" in component
    assert "getManagementDashboard" in component


def test_management_dashboard_frontend_types_are_aggregate_only() -> None:
    types = _read(FRONTEND / "types" / "cdasManagementDashboard.ts")

    for banned in (
        "client_name",
        "client_reference",
        "employee_no",
        "nid",
        "notes",
        "reason_details",
    ):
        assert banned not in types

    for expected in (
        "active_opportunities",
        "overdue_follow_ups",
        "duplicate_candidate_pairs",
        "material_changes",
        "next_12_months",
        "pipeline_stages",
        "failure_reasons",
        "forecast_months",
    ):
        assert expected in types


def test_management_dashboard_has_no_database_migration_or_decision_write_path() -> None:
    service = _read(BACKEND / "services" / "cdas_management_dashboard.py")
    router = _read(BACKEND / "routers" / "cdas_management_dashboard.py")

    assert "aggregate workflow information only" in service
    assert '"aggregate_only": True' in service
    assert '"automated_credit_decision": False' in service
    assert "approval, eligibility, pricing" in service
    assert "db.add(" not in router
    assert "db.commit(" not in router
