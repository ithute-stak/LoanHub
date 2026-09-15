from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_advanced_search_route_is_registered_company_scoped_and_read_only() -> None:
    router = _read(BACKEND / "routers" / "cdas_advanced_search.py")
    api_router = _read(BACKEND / "api" / "v1" / "router.py")

    assert '@router.get("/advanced-search")' in router
    assert "_require_company_member(context)" in router
    assert "CdasAnalysisRecord.company_id == context.company_id" in router
    assert "CdasBookingOpportunity.company_id == context.company_id" in router
    assert "CompanyStaff.company_id == context.company_id" in router
    assert "cdas_advanced_search.router" in api_router
    assert "db.add(" not in router
    assert "db.commit(" not in router
    assert "db.delete(" not in router
    assert 'key != "analysis_snapshot"' in router


def test_advanced_search_validates_ranges_and_exposes_filters() -> None:
    router = _read(BACKEND / "routers" / "cdas_advanced_search.py")

    for phrase in (
        "booking_from cannot be after booking_to",
        "analyzed_from cannot be after analyzed_to",
        "min_capacity cannot exceed max_capacity",
        "min_deduction cannot exceed max_deduction",
        "assigned_to_user_id",
        "pipeline_stage",
        "quality",
        "min_capacity",
        "max_capacity",
        "min_deduction",
        "max_deduction",
    ):
        assert phrase in router


def test_advanced_search_frontend_api_route_and_navigation_are_wired() -> None:
    api = _read(FRONTEND / "api" / "cdasBooking.ts")
    layout = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx")
    page = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "advanced-search" / "page.tsx")

    assert '"/cdas-booking/advanced-search"' in api
    assert "CdasAdvancedSearchParams" in api
    assert "CdasAdvancedSearchResponse" in api
    assert 'href="/company/cdas-booking/advanced-search"' in layout
    assert "Advanced Search" in layout
    assert "CdasAdvancedSearchView" in page


def test_advanced_search_ui_contains_archive_and_workflow_filters() -> None:
    component = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "CdasAdvancedSearch.tsx"
    )

    for phrase in (
        "CDAS Advanced Search & Filters",
        "Analysis Archive",
        "Booking Opportunities",
        "Assigned officer",
        "Data quality",
        "Booking from",
        "Analyzed from",
        "Min capacity",
        "Min deduction",
        "Unassigned",
        "Clear filters",
    ):
        assert phrase in component

    assert "cdasBookingApi.advancedSearch" in component
    assert "cdasBookingApi.saveOpportunity" not in component
    assert "cdasBookingApi.updatePipelineStage" not in component
