from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_bulk_processing_backend_route_is_registered_and_company_scoped() -> None:
    router = _read(BACKEND / "routers" / "cdas_bulk_processing.py")
    api_router = _read(BACKEND / "api" / "v1" / "router.py")

    assert '@router.post("/bulk-analyze")' in router
    assert "MAX_BULK_ITEMS = 25" in router
    assert "MAX_BULK_RAW_TEXT_CHARS = 1_000_000" in router
    assert "_require_company_member(context)" in router
    assert "company_id=context.company_id" in router
    assert "analyzed_by_user_id=context.user.id" in router
    assert "save_or_get_analysis_record" in router
    assert "build_bulk_error_item" in router
    assert "save_or_update_opportunity_from_analysis" not in router
    assert "cdas_bulk_processing.router" in api_router


def test_bulk_processing_frontend_api_route_and_navigation_are_wired() -> None:
    api = _read(FRONTEND / "api" / "cdasBooking.ts")
    layout = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx")
    page = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "bulk-processing" / "page.tsx")

    assert '"/cdas-booking/bulk-analyze"' in api
    assert "CdasBulkAnalyzeRequest" in api
    assert "CdasBulkAnalyzeResponse" in api
    assert 'href="/company/cdas-booking/bulk-processing"' in layout
    assert "Bulk Processing" in layout
    assert "CdasBulkProcessingView" in page


def test_bulk_processing_ui_explains_limits_dedupe_and_no_auto_opportunity_creation() -> None:
    component = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "CdasBulkProcessing.tsx"
    )

    for phrase in (
        "Bulk CDAS Processing",
        "up to 25 client CDAS records",
        "independent success or error result",
        "Exact duplicates reuse the existing archive",
        "does not automatically create booking opportunities",
        "New archives",
        "Archive reused",
        "Review required",
    ):
        assert phrase in component

    assert "rows.length >= 25" in component
    assert "raw_text: row.rawText" in component
    assert "cdasBookingApi.bulkAnalyze" in component
    assert "cdasBookingApi.saveOpportunity" not in component


def test_bulk_result_types_do_not_expose_raw_cdas_text() -> None:
    types = _read(FRONTEND / "types" / "cdasBulkProcessing.ts")
    service = _read(BACKEND / "services" / "cdas_bulk_processing.py")

    assert "raw_text" not in types
    assert '"raw_text"' not in service
