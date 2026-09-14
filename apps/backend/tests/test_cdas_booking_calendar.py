from datetime import date

from services.cdas_booking_calendar import build_booking_calendar


TODAY = date(2026, 9, 14)


def _opportunity(
    identifier: str,
    booking_date: str | None,
    *,
    state: str = "UPCOMING",
    client_name: str | None = None,
) -> dict:
    return {
        "id": identifier,
        "client_name": client_name or f"Client {identifier}",
        "client_reference": f"EMP-{identifier}",
        "state": state,
        "booking_open_date": booking_date,
        "alert_start_date": booking_date,
        "opportunity_agency_name": "Example Agency",
        "opportunity_item_code": "2595",
        "opportunity_reference_no": f"REF-{identifier}",
        "opportunity_expiry_date": "2027-12-31",
        "opportunity_deduction_amount": 500.0,
        "booked_at": "2026-09-10T10:00:00" if state == "BOOKED" else None,
        "analysis_snapshot": {},
    }


def test_calendar_classifies_overdue_today_future_unscheduled_and_booked():
    opportunities = [
        _opportunity("overdue", "2026-09-13", state="BOOK_NOW"),
        _opportunity("today", "2026-09-14", state="BOOK_NOW"),
        _opportunity("week", "2026-09-18"),
        _opportunity("thirty", "2026-10-01"),
        _opportunity("ninety", "2026-11-15"),
        _opportunity("later", "2027-01-01"),
        _opportunity("unscheduled", None),
        _opportunity("booked", "2026-09-10", state="BOOKED"),
    ]

    calendar = build_booking_calendar(opportunities, today=TODAY)
    buckets = {event["id"]: event["bucket"] for event in calendar["events"]}

    assert buckets == {
        "overdue": "OVERDUE",
        "today": "TODAY",
        "week": "THIS_WEEK",
        "thirty": "NEXT_30_DAYS",
        "ninety": "NEXT_90_DAYS",
        "later": "LATER",
        "unscheduled": "UNSCHEDULED",
        "booked": "BOOKED",
    }


def test_calendar_summary_uses_cumulative_planning_windows():
    opportunities = [
        _opportunity("overdue", "2026-09-13", state="BOOK_NOW"),
        _opportunity("today", "2026-09-14", state="BOOK_NOW"),
        _opportunity("week", "2026-09-18"),
        _opportunity("thirty", "2026-10-01"),
        _opportunity("ninety", "2026-11-15"),
        _opportunity("later", "2027-01-01"),
        _opportunity("unscheduled", None),
        _opportunity("booked", "2026-09-10", state="BOOKED"),
    ]

    summary = build_booking_calendar(opportunities, today=TODAY)["summary"]

    assert summary["open"] == 7
    assert summary["overdue"] == 1
    assert summary["today"] == 1
    assert summary["this_week"] == 2
    assert summary["next_30_days"] == 3
    assert summary["next_90_days"] == 4
    assert summary["later"] == 1
    assert summary["unscheduled"] == 1
    assert summary["booked"] == 1


def test_same_saved_booking_rolls_from_future_to_today_to_overdue_without_mutation():
    saved = _opportunity("rolling", "2026-09-14", state="UPCOMING")

    before = build_booking_calendar([saved], today=date(2026, 9, 13))["events"][0]
    due = build_booking_calendar([saved], today=date(2026, 9, 14))["events"][0]
    after = build_booking_calendar([saved], today=date(2026, 9, 15))["events"][0]

    assert before["bucket"] == "NEXT_30_DAYS"
    assert before["days_from_today"] == 1
    assert due["bucket"] == "TODAY"
    assert due["days_from_today"] == 0
    assert after["bucket"] == "OVERDUE"
    assert after["days_from_today"] == -1
    assert saved["booking_open_date"] == "2026-09-14"


def test_booked_records_never_become_overdue_even_when_booking_date_is_past():
    booked = _opportunity("booked", "2026-01-01", state="BOOKED")

    event = build_booking_calendar([booked], today=TODAY)["events"][0]

    assert event["bucket"] == "BOOKED"
    assert event["is_overdue"] is False
