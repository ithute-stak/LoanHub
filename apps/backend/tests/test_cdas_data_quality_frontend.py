from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
ROUTER = BACKEND / "routers" / "cdas_data_quality.py"
SERVICE = BACKEND / "services" / "cdas_data_quality.py"
API_ROUTER = BACKEND / "api" / "v1" / "router.py"
VIEW = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasDataQualityCentre.tsx"
PAGE = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "data-quality" / "page.tsx"
LAYOUT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = FRONTEND / "api" / "cdasBooking.ts"


def test_data_quality_endpoint_is_company_scoped_and_uses_detailed_latest_profiles():
    source = ROUTER.read_text(encoding="utf-8")
    registry = API_ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/data-quality")' in source
    assert "CdasAnalysisRecord.company_id == context.company_id" in source
    assert "CdasBookingOpportunity.company_id == context.company_id" in source
    assert "include_detail=True" in source
    assert "build_client_profiles" in source
    assert "build_data_quality_centre" in source
    assert "cdas_data_quality.router" in registry


def test_data_quality_engine_is_diagnostic_only_and_tracks_expected_categories():
    source = SERVICE.read_text(encoding="utf-8")

    for category in (
        "REVIEW_REQUIRED",
        "MISSING_EXPIRY",
        "DATE_CONFLICT",
        "MISSING_STRONG_IDENTIFIER",
        "MISSING_EMPLOYER",
        "MISSING_CDAS_AGENCY",
        "CAPACITY_UNKNOWN",
        "MISSING_DEDUCTION_REFERENCE",
        "INVALID_DEDUCTION_AMOUNT",
    ):
        assert category in source
    assert "db.commit" not in source
    assert "db.add" not in source
    assert "db.delete" not in source


def test_frontend_exposes_quality_score_blockers_categories_and_exact_deduction_context():
    view = VIEW.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    for label in (
        "CDAS Data Quality Centre",
        "Blocker clients",
        "Affected monthly value",
        "Needs attention",
        "Blockers only",
        "Quality ",
        "Monthly deduction",
        "Effective / expiry",
    ):
        assert label in view
    assert "diagnostic only" in view
    assert "CdasDataQualityCentreView" in page
    assert "/company/cdas-booking/data-quality" in layout
    assert '"/cdas-booking/data-quality"' in api
    assert "getDataQuality" in api


def test_step_11_adds_no_database_migration():
    versions = BACKEND / "alembic" / "versions"
    assert not any("data_quality" in path.name for path in versions.glob("*.py"))
