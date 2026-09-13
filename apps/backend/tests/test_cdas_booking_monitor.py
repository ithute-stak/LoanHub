from datetime import date

from database.models.cdas_booking import CdasBookingOpportunity
from services.cdas_booking_monitor import opportunity_state, serialize_opportunity


def make_opportunity(**values):
    defaults = {
        "status": "monitoring",
        "booking_lead_months": 6,
        "alert_lead_days": 3,
        "booking_open_date": date(2027, 2, 1),
        "total_monthly_deductions": 0,
        "own_monthly_deductions": 0,
        "competitor_monthly_deductions": 0,
        "analysis_snapshot": {},
    }
    defaults.update(values)
    return CdasBookingOpportunity(**defaults)


def test_opportunity_is_upcoming_before_booking_window():
    item = make_opportunity()
    assert opportunity_state(item, date(2027, 1, 29)) == "UPCOMING"
    result = serialize_opportunity(item, date(2027, 1, 29))
    assert result["days_until_booking"] == 3


def test_opportunity_becomes_book_now_on_open_date():
    item = make_opportunity()
    assert opportunity_state(item, date(2027, 2, 1)) == "BOOK_NOW"


def test_booked_status_stops_active_queue():
    item = make_opportunity(status="booked")
    assert opportunity_state(item, date(2027, 1, 1)) == "BOOKED"
