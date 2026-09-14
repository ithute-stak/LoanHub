from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
COMPONENT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasMaxLoanCalculator.tsx"
PAGE = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "max-loan" / "page.tsx"
LAYOUT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = FRONTEND / "api" / "cdasBooking.ts"
ROUTER = ROOT / "backend" / "routers" / "cdas_booking_calendar.py"


def test_reference_calculator_route_and_navigation_exist():
    component = COMPONENT.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")

    assert "CDAS Loan Reference Calculator" in component
    assert "Monthly capacity" in component
    assert "Calculate reference amount" in component
    assert "does not read a borrower record" in component
    assert "does not" in component and "approval" in component
    assert "CdasMaxLoanCalculator" in page
    assert 'href="/company/cdas-booking/max-loan"' in layout
    assert "Loan Reference Calculator" in layout


def test_reference_calculator_api_uses_manual_capacity_not_opportunity_id():
    api = API.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")

    assert '"/cdas-booking/loan-capacity"' in api
    assert '@router.post("/loan-capacity")' in router
    assert "monthly_capacity" in router
    endpoint = router.split('@router.post("/loan-capacity")', 1)[1]
    assert "opportunity_id" not in endpoint
    assert "calculate_reference_max_principal" in endpoint


def test_reference_calculator_explains_the_math_components():
    component = COMPONENT.read_text(encoding="utf-8")

    assert "Reference principal" in component
    assert "Installment budget" in component
    assert "Financed balance" in component
    assert "Insurance amount" in component
    assert "Monthly total" in component
    assert "calculation_note" in component
