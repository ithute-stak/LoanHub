from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIORITY_VIEW = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasBookingPriorityQueue.tsx"
PRIORITY_PAGE = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "priorities" / "page.tsx"
LAYOUT = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = ROOT / "frontend" / "api" / "cdasBooking.ts"
ROUTER = ROOT / "backend" / "routers" / "cdas_booking_calendar.py"


def test_priority_queue_route_and_navigation_are_exposed():
    layout = LAYOUT.read_text(encoding="utf-8")
    page = PRIORITY_PAGE.read_text(encoding="utf-8")

    assert "/company/cdas-booking/priorities" in layout
    assert "Priority Queue" in layout
    assert "CdasBookingPriorityQueueView" in page


def test_frontend_calls_tenant_priority_endpoint_and_shows_explainable_breakdown():
    api = API.read_text(encoding="utf-8")
    source = PRIORITY_VIEW.read_text(encoding="utf-8")

    assert '"/cdas-booking/priorities"' in api
    assert "CDAS Booking Priority Queue" in source
    assert "priority / 100" in source
    assert "Timing urgency" in source
    assert "Opportunity value" in source
    assert "Booking readiness" in source
    assert "Data quality" in source
    assert "Critical" in source
    assert "High priority" in source
    assert "Mark booking complete" in source


def test_priority_endpoint_reuses_company_scope_and_deduplication():
    source = ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/priorities")' in source
    assert "_require_company_member(context)" in source
    assert "CdasBookingOpportunity.company_id == context.company_id" in source
    assert "dedupe_serialized_opportunities" in source
    assert "build_booking_priority_queue" in source
