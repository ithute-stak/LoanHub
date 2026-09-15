from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
SERVICE = BACKEND / "services" / "cdas_change_detection.py"
ROUTER = BACKEND / "routers" / "cdas_change_detection.py"
API_ROUTER = BACKEND / "api" / "v1" / "router.py"
VIEW = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasChangeDetection.tsx"
PAGE = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "changes" / "page.tsx"
LAYOUT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = FRONTEND / "api" / "cdasBooking.ts"


def test_change_detection_api_is_read_only_and_company_scoped():
    source = ROUTER.read_text(encoding="utf-8")
    registry = API_ROUTER.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert '@router.get("/changes")' in source
    assert "CdasAnalysisRecord.company_id == context.company_id" in source
    assert "build_change_detection(records)" in source
    assert "cdas_change_detection.router" in registry
    assert "db.add(" not in source
    assert "db.commit(" not in source
    assert "_build_groups" in service


def test_change_service_exposes_explainable_field_and_deduction_diffs():
    source = SERVICE.read_text(encoding="utf-8")

    for kind in ("FIELD_CHANGED", "DEDUCTION_ADDED", "DEDUCTION_REMOVED", "DEDUCTION_MODIFIED"):
        assert kind in source
    for field in ("decision", "assessed_available_amount", "next_possible_booking_date", "current_agency_name", "data_quality_issue_count"):
        assert field in source
    assert '"impact": "MATERIAL"' in source
    assert "changed_fields" in source


def test_frontend_exposes_change_summary_search_material_filter_and_before_after():
    view = VIEW.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    for label in ("CDAS Change Detection", "Clients compared", "Clients with material changes", "Total changes", "Material changes", "Material only", "All comparisons", "Before", "After"):
        assert label in view
    assert "Change detection requires at least two archived CDAS analyses" in view
    assert "CdasChangeDetectionView" in page
    assert "/company/cdas-booking/changes" in layout
    assert '"/cdas-booking/changes"' in api
    assert "getChanges" in api
