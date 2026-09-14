from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
ROUTER = BACKEND / "routers" / "cdas_booking_calendar.py"
API_ROUTER = BACKEND / "api" / "v1" / "router.py"
API = FRONTEND / "api" / "cdasBooking.ts"
CDAS_ROOT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking"
LAYOUT = CDAS_ROOT / "layout.tsx"
PAGE = CDAS_ROOT / "calendar" / "page.tsx"
CALENDAR = CDAS_ROOT / "CdasBookingCalendar.tsx"


def test_booking_calendar_router_is_registered_and_company_scoped():
    router = ROUTER.read_text(encoding="utf-8")
    registry = API_ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/calendar")' in router
    assert "CdasBookingOpportunity.company_id == context.company_id" in router
    assert "dedupe_serialized_opportunities" in router
    assert "cdas_booking_calendar.router" in registry


def test_cdas_workspace_exposes_booking_calendar_route():
    layout = LAYOUT.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")

    assert "/company/cdas-booking/calendar" in layout
    assert "Booking Calendar" in layout
    assert "CdasBookingCalendarView" in page


def test_calendar_ui_exposes_operational_planning_views_and_booking_completion():
    source = CALENDAR.read_text(encoding="utf-8")

    for label in (
        "Automatic CDAS Booking Calendar",
        "Overdue",
        "Today",
        "This Week",
        "Next 30 Days",
        "Next 90 Days",
        "Unscheduled",
        "Booked",
        "Mark booking complete",
    ):
        assert label in source

    assert "cdasBookingApi.markBooked" in source


def test_frontend_calendar_uses_dedicated_calendar_api():
    source = API.read_text(encoding="utf-8")

    assert "getBookingCalendar" in source
    assert '"/cdas-booking/calendar"' in source
