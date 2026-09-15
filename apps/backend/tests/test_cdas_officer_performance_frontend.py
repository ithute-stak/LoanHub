from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_officer_performance_endpoint_is_company_scoped_and_registered() -> None:
    router = _read(BACKEND / "routers" / "cdas_officer_performance.py")
    api_router = _read(BACKEND / "api" / "v1" / "router.py")

    assert '@router.get("/officer-performance")' in router
    assert "_require_company_member(context)" in router
    assert "CdasBookingOpportunity.company_id == context.company_id" in router
    assert "CdasOpportunityContact.company_id == context.company_id" in router
    assert "CdasBookingFailure.company_id == context.company_id" in router
    assert "CompanyStaff.company_id == context.company_id" in router
    assert "cdas_officer_performance.router" in api_router


def test_officer_performance_is_read_only_and_uses_existing_assignment_endpoint() -> None:
    router = _read(BACKEND / "routers" / "cdas_officer_performance.py")
    api = _read(FRONTEND / "api" / "cdasBooking.ts")

    assert "db.add(" not in router
    assert "db.delete(" not in router
    assert "db.commit(" not in router
    assert '"/cdas-booking/officer-performance"' in api
    assert "assignOpportunity" in api
    assert "/assignment" in api


def test_officer_performance_frontend_explains_metrics_without_ranking_staff() -> None:
    component = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "CdasOfficerPerformance.tsx"
    )
    layout = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "layout.tsx"
    )
    page = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "officer-performance"
        / "page.tsx"
    )

    for phrase in (
        "CDAS Officer Assignment & Performance",
        "Assigned open",
        "Unassigned open",
        "Book Now open",
        "Overdue follow-ups",
        "Contacts · 30 days",
        "Uncontacted open",
        "Unassigned CDAS opportunities",
    ):
        assert phrase in component

    assert "No composite staff score" in component
    assert "credit-quality ranking" in component
    assert "performance_score" not in component
    assert "approval_rate" not in component
    assert 'href="/company/cdas-booking/officer-performance"' in layout
    assert "Officer Performance" in layout
    assert "CdasOfficerPerformanceView" in page


def test_officer_performance_adds_no_database_migration() -> None:
    service = _read(BACKEND / "services" / "cdas_officer_performance.py")
    types = _read(FRONTEND / "types" / "cdasOfficerPerformance.ts")

    assert "build_officer_performance" in service
    assert "performance_score" not in service
    assert "approval_rate" not in service
    assert "CdasOfficerPerformanceWorkspace" in types
