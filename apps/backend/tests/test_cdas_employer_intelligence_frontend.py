from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
SERVICE = BACKEND / "services" / "cdas_employer_intelligence.py"
ROUTER = BACKEND / "routers" / "cdas_booking_calendar.py"
VIEW = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasEmployerIntelligence.tsx"
PAGE = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "employer-intelligence" / "page.tsx"
LAYOUT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = FRONTEND / "api" / "cdasBooking.ts"


def test_employer_intelligence_endpoint_uses_latest_company_profile_projection():
    source = ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/employer-intelligence")' in source
    assert "CdasAnalysisRecord.company_id == context.company_id" in source
    assert "build_client_profiles(analyses, [], include_detail=True)" in source
    assert "build_employer_intelligence(profiles, today=local_today())" in source


def test_employer_intelligence_payload_is_aggregate_only():
    source = SERVICE.read_text(encoding="utf-8")

    assert '"employer_name"' in source
    assert '"client_count"' in source
    assert '"competitor_monthly_value"' in source
    assert '"available_capacity_total"' in source
    assert '"decision_counts"' in source
    assert '"top_competitor_agencies"' in source
    assert '"client_name"' not in source
    assert '"client_reference"' not in source
    assert '"employee_no"' not in source
    assert '"nid"' not in source


def test_employer_intelligence_frontend_exposes_management_metrics_and_privacy_message():
    view = VIEW.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    for label in (
        "CDAS Employer Intelligence",
        "Competitor monthly value",
        "Book now opportunity",
        "Next 90 days",
        "Available CDAS capacity",
        "Decision mix",
        "Top competitor agencies",
        "Opportunities only",
    ):
        assert label in view
    assert "does not return client names or references" in view
    assert "CdasEmployerIntelligenceView" in page
    assert "/company/cdas-booking/employer-intelligence" in layout
    assert '"/cdas-booking/employer-intelligence"' in api
    assert "getEmployerIntelligence" in api


def test_step_12_adds_no_database_migration():
    versions = BACKEND / "alembic" / "versions"
    assert not any("employer_intelligence" in path.name for path in versions.glob("*.py"))
