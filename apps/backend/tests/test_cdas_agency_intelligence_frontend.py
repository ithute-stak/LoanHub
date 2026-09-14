from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIEW = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasAgencyIntelligence.tsx"
PAGE = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "agency-intelligence" / "page.tsx"
LAYOUT = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = ROOT / "frontend" / "api" / "cdasBooking.ts"
ROUTER = ROOT / "backend" / "routers" / "cdas_booking_calendar.py"


def test_agency_intelligence_route_and_navigation_are_exposed():
    layout = LAYOUT.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")

    assert "/company/cdas-booking/agency-intelligence" in layout
    assert "Agency Intelligence" in layout
    assert "CdasAgencyIntelligenceView" in page


def test_frontend_calls_agency_intelligence_endpoint_and_shows_management_metrics():
    api = API.read_text(encoding="utf-8")
    source = VIEW.read_text(encoding="utf-8")

    assert '"/cdas-booking/agency-intelligence"' in api
    assert "CDAS Agency Intelligence" in source
    assert "Competitor monthly value" in source
    assert "Own monthly value" in source
    assert "Book now opportunity" in source
    assert "Next 30 days" in source
    assert "Next 90 days" in source
    assert "Competitor share" in source
    assert "Search agencies" in source


def test_agency_endpoint_is_company_scoped_and_uses_latest_client_profiles():
    source = ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/agency-intelligence")' in source
    assert "_require_company_member(context)" in source
    assert "CdasAnalysisRecord.company_id == context.company_id" in source
    assert "build_client_profiles(analyses, [], include_detail=True)" in source
    assert "build_agency_intelligence" in source
