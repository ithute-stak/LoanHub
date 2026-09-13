from datetime import date, datetime
from types import SimpleNamespace

from services.cdas_booking_monitor import booking_window_dates, monitor_phase


def test_booking_alert_starts_three_days_before_window():
    booking_open, alert_start = booking_window_dates(date(2027, 8, 1), 6)

    assert booking_open == date(2027, 2, 1)
    assert alert_start == date(2027, 1, 29)


def test_monitor_phase_moves_from_upcoming_to_alerting_to_book_now():
    monitor = SimpleNamespace(
        booked_at=None,
        alert_start_date=date(2027, 1, 29),
        booking_open_date=date(2027, 2, 1),
    )

    assert monitor_phase(monitor, as_of=date(2027, 1, 28)) == "UPCOMING"
    assert monitor_phase(monitor, as_of=date(2027, 1, 29)) == "ALERTING"
    assert monitor_phase(monitor, as_of=date(2027, 2, 1)) == "BOOK_NOW"

    monitor.booked_at = datetime(2027, 2, 2, 9, 0)
    assert monitor_phase(monitor, as_of=date(2027, 2, 3)) == "BOOKED"
