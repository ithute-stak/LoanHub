from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _iso_date(value: Any) -> str | None:
    parsed = _as_date(value)
    return parsed.isoformat() if parsed else None


def _iso_datetime(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _exclusive_bucket(item: dict[str, Any], *, today: date, week_end: date) -> str:
    if str(item.get("state") or "").upper() == "BOOKED":
        return "BOOKED"

    booking_date = _as_date(item.get("booking_open_date"))
    if booking_date is None:
        return "UNSCHEDULED"
    if booking_date < today:
        return "OVERDUE"
    if booking_date == today:
        return "TODAY"
    if booking_date <= week_end:
        return "THIS_WEEK"
    if booking_date <= today + timedelta(days=30):
        return "NEXT_30_DAYS"
    if booking_date <= today + timedelta(days=90):
        return "NEXT_90_DAYS"
    return "LATER"


def _calendar_event(item: dict[str, Any], *, today: date, week_end: date) -> dict[str, Any]:
    booking_date = _as_date(item.get("booking_open_date"))
    state = str(item.get("state") or "UPCOMING").upper()
    days_from_today = (booking_date - today).days if booking_date else None
    return {
        "id": str(item.get("id") or ""),
        "client_name": item.get("client_name"),
        "client_reference": item.get("client_reference"),
        "agency_name": item.get("opportunity_agency_name"),
        "item_code": item.get("opportunity_item_code"),
        "reference_no": item.get("opportunity_reference_no"),
        "deduction_amount": float(item.get("opportunity_deduction_amount") or 0),
        "booking_date": booking_date.isoformat() if booking_date else None,
        "alert_start_date": _iso_date(item.get("alert_start_date")),
        "expiry_date": _iso_date(item.get("opportunity_expiry_date")),
        "booked_at": _iso_datetime(item.get("booked_at")),
        "state": state,
        "bucket": _exclusive_bucket(item, today=today, week_end=week_end),
        "days_from_today": days_from_today,
        "is_overdue": bool(state != "BOOKED" and booking_date and booking_date < today),
        "analysis_snapshot": item.get("analysis_snapshot") or {},
    }


def build_booking_calendar(
    opportunities: Iterable[dict[str, Any]],
    *,
    today: date,
) -> dict[str, Any]:
    """Build an automatic calendar projection from saved CDAS opportunities.

    The source records remain the booking opportunities table. Calendar state is
    calculated at read time so a future booking naturally becomes Today and then
    Overdue without a background mutation or second schedule table.
    """
    week_end = today + timedelta(days=6 - today.weekday())
    day_30 = today + timedelta(days=30)
    day_90 = today + timedelta(days=90)

    events = [
        _calendar_event(item, today=today, week_end=week_end)
        for item in opportunities
    ]

    def event_sort_key(event: dict[str, Any]) -> tuple[int, str, str]:
        bucket_rank = {
            "OVERDUE": 0,
            "TODAY": 1,
            "THIS_WEEK": 2,
            "NEXT_30_DAYS": 3,
            "NEXT_90_DAYS": 4,
            "LATER": 5,
            "UNSCHEDULED": 6,
            "BOOKED": 7,
        }
        return (
            bucket_rank.get(str(event.get("bucket")), 99),
            str(event.get("booking_date") or "9999-12-31"),
            str(event.get("client_name") or event.get("client_reference") or ""),
        )

    events.sort(key=event_sort_key)

    open_events = [event for event in events if event["state"] != "BOOKED"]
    dated_open = [event for event in open_events if event["booking_date"]]

    def in_range(event: dict[str, Any], start: date, end: date) -> bool:
        value = _as_date(event.get("booking_date"))
        return bool(value and start <= value <= end)

    summary = {
        "open": len(open_events),
        "overdue": sum(1 for event in open_events if event["is_overdue"]),
        "today": sum(1 for event in open_events if _as_date(event["booking_date"]) == today),
        "this_week": sum(1 for event in open_events if in_range(event, today, week_end)),
        "next_30_days": sum(1 for event in open_events if in_range(event, today, day_30)),
        "next_90_days": sum(1 for event in open_events if in_range(event, today, day_90)),
        "later": sum(
            1
            for event in dated_open
            if (_as_date(event["booking_date"]) or today) > day_90
        ),
        "unscheduled": sum(1 for event in open_events if not event["booking_date"]),
        "booked": sum(1 for event in events if event["state"] == "BOOKED"),
    }

    return {
        "as_of": today.isoformat(),
        "week_end": week_end.isoformat(),
        "next_30_days_end": day_30.isoformat(),
        "next_90_days_end": day_90.isoformat(),
        "summary": summary,
        "events": events,
        "total": len(events),
    }
