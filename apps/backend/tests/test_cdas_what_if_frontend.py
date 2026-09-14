from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
COMPONENT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasWhatIfSimulator.tsx"
PAGE = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "simulator" / "page.tsx"
LAYOUT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = FRONTEND / "api" / "cdasBooking.ts"
ROUTER = ROOT / "backend" / "routers" / "cdas_booking_calendar.py"


def test_cdas_what_if_workspace_route_and_navigation_exist():
    component = COMPONENT.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")

    assert "CDAS What-If Simulator" in component
    assert "Installment only" in component
    assert "Loan scenario" in component
    assert "Run what-if simulation" in component
    assert "Saved future deduction windows" in component
    assert "does not modify the saved opportunity" in component
    assert "CdasWhatIfSimulator" in page
    assert 'href="/company/cdas-booking/simulator"' in layout
    assert "What-If Simulator" in layout


def test_frontend_calls_tenant_scoped_simulator_endpoint():
    api = API.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")

    assert '"/cdas-booking/simulator"' in api
    assert '@router.post("/simulator")' in router
    assert "CdasBookingOpportunity.company_id == context.company_id" in router
    assert "simulate_what_if" in router


def test_simulator_surfaces_capacity_shortfall_release_and_quality_context():
    component = COMPONENT.read_text(encoding="utf-8")

    assert "Current CDAS capacity" in component
    assert "Remaining capacity" in component
    assert "Current shortfall" in component
    assert "Earliest estimated fit" in component
    assert "Confidence:" in component
    assert "result.warnings" in component
    assert "projection_note" in component
