from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_forecast_route_api_and_navigation_are_wired() -> None:
    api = _read(FRONTEND / "api" / "cdasBooking.ts")
    layout = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx")
    page = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "forecast" / "page.tsx")
    router = _read(BACKEND / "routers" / "cdas_booking_calendar.py")

    assert '"/cdas-booking/forecast"' in api
    assert 'href="/company/cdas-booking/forecast"' in layout
    assert "CDAS Forecast" in layout
    assert "CdasForecastView" in page
    assert '@router.get("/forecast")' in router
    assert "_require_company_member(context)" in router
    assert "CdasAnalysisRecord.company_id == context.company_id" in router
    assert "build_client_profiles(analyses, [], include_detail=True)" in router
    assert "build_cdas_forecast(profiles, today=local_today(), horizon_months=12)" in router


def test_forecast_ui_states_scope_and_forecast_limits() -> None:
    component = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "CdasForecast.tsx"
    )

    for phrase in (
        "CDAS Forecast",
        "Book Now backlog",
        "Next 3 months",
        "Next 6 months",
        "12-month scheduled",
        "Quality-excluded",
        "12-month booking-window outlook",
        "Top employers in forecast",
        "Top competitor agencies in forecast",
    ):
        assert phrase in component

    assert "not approval, eligibility, loan amount, disbursement or revenue" in component
    assert "own-company deductions are not treated as competitor opportunities" in component
    assert "invalid or excluded CDAS rows" in component


def test_forecast_types_do_not_expose_client_identity_fields() -> None:
    types = _read(FRONTEND / "types" / "cdasForecast.ts")

    assert "client_name" not in types
    assert "client_reference" not in types
    assert "employee_no" not in types
    assert "nid" not in types


def test_forecast_does_not_add_a_database_migration() -> None:
    service = _read(BACKEND / "services" / "cdas_forecast.py")
    router = _read(BACKEND / "routers" / "cdas_booking_calendar.py")

    assert "build_cdas_forecast" in service
    assert "db.add(" not in router
    assert "db.delete(" not in router
