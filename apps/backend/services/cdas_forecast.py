from __future__ import annotations

from datetime import date, datetime
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


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _month_label(value: date) -> str:
    return value.strftime("%b %Y")


def _money(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _name(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def _concentration_item(store: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    key = name.casefold()
    return store.setdefault(
        key,
        {
            "name": name,
            "book_now_count": 0,
            "book_now_value": 0.0,
            "scheduled_count": 0,
            "scheduled_value": 0.0,
        },
    )


def _finalize_concentration(store: dict[str, dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for item in store.values():
        total_value = float(item["book_now_value"]) + float(item["scheduled_value"])
        values.append(
            {
                "name": item["name"],
                "book_now_count": int(item["book_now_count"]),
                "book_now_value": round(float(item["book_now_value"]), 2),
                "scheduled_count": int(item["scheduled_count"]),
                "scheduled_value": round(float(item["scheduled_value"]), 2),
                "total_opportunity_value": round(total_value, 2),
            }
        )
    values.sort(
        key=lambda item: (
            -float(item["total_opportunity_value"]),
            -int(item["scheduled_count"] + item["book_now_count"]),
            str(item["name"]).casefold(),
        )
    )
    return values[:limit]


def build_cdas_forecast(
    client_profiles: Iterable[dict[str, Any]],
    *,
    today: date,
    horizon_months: int = 12,
) -> dict[str, Any]:
    """Build an aggregate booking-window forecast from each client's latest CDAS profile.

    This is a deterministic operational schedule based on saved booking-open dates. It does not
    estimate loan approval, borrower eligibility, disbursement value or revenue probability.
    """
    if horizon_months < 1 or horizon_months > 24:
        raise ValueError("Forecast horizon must be between 1 and 24 months")

    start_month = _month_start(today)
    horizon_end = _add_months(start_month, horizon_months)
    buckets: dict[str, dict[str, Any]] = {}
    for offset in range(horizon_months):
        month = _add_months(start_month, offset)
        buckets[_month_key(month)] = {
            "month": _month_key(month),
            "label": _month_label(month),
            "opportunity_count": 0,
            "monthly_deduction_value": 0.0,
            "client_keys": set(),
            "employers": set(),
            "agencies": set(),
        }

    book_now_count = 0
    book_now_value = 0.0
    book_now_clients: set[str] = set()
    future_clients: set[str] = set()
    excluded_quality_count = 0
    excluded_quality_value = 0.0
    unscheduled_count = 0
    unscheduled_value = 0.0
    later_count = 0
    later_value = 0.0
    missing_employer_clients: set[str] = set()
    employers: dict[str, dict[str, Any]] = {}
    agencies: dict[str, dict[str, Any]] = {}

    for profile in client_profiles:
        client_key = str(profile.get("client_key") or "").strip()
        employer_raw = str(profile.get("employer") or "").strip()
        employer = employer_raw or "Unknown employer"
        if client_key and not employer_raw:
            missing_employer_clients.add(client_key)

        for row in profile.get("current_deductions") or []:
            if not bool(row.get("reported_active")):
                continue
            if bool(row.get("is_own_booking")):
                continue

            amount = _money(row.get("deduction_amount"))
            quality = str(row.get("data_quality_status") or "OK").upper()
            excluded = bool(row.get("excluded_from_booking")) or quality != "OK"
            agency = _name(row.get("agency_name"), "Unknown agency")

            if excluded:
                excluded_quality_count += 1
                excluded_quality_value += amount
                continue

            booking_date = _as_date(row.get("booking_open_date"))
            booking_status = str(row.get("booking_status") or "").upper()
            employer_entry = _concentration_item(employers, employer)
            agency_entry = _concentration_item(agencies, agency)

            if booking_status == "BOOK_NOW" or (booking_date and booking_date <= today):
                book_now_count += 1
                book_now_value += amount
                if client_key:
                    book_now_clients.add(client_key)
                for entry in (employer_entry, agency_entry):
                    entry["book_now_count"] += 1
                    entry["book_now_value"] += amount
                continue

            if booking_date is None:
                unscheduled_count += 1
                unscheduled_value += amount
                continue

            if booking_date >= horizon_end:
                later_count += 1
                later_value += amount
                continue

            month_key = _month_key(_month_start(booking_date))
            bucket = buckets.get(month_key)
            if bucket is None:
                # A valid date earlier than the current month would already be Book Now.
                continue

            bucket["opportunity_count"] += 1
            bucket["monthly_deduction_value"] += amount
            bucket["employers"].add(employer)
            bucket["agencies"].add(agency)
            if client_key:
                bucket["client_keys"].add(client_key)
                future_clients.add(client_key)
            for entry in (employer_entry, agency_entry):
                entry["scheduled_count"] += 1
                entry["scheduled_value"] += amount

    months: list[dict[str, Any]] = []
    for bucket in buckets.values():
        months.append(
            {
                "month": bucket["month"],
                "label": bucket["label"],
                "opportunity_count": int(bucket["opportunity_count"]),
                "client_count": len(bucket["client_keys"]),
                "monthly_deduction_value": round(float(bucket["monthly_deduction_value"]), 2),
                "employer_count": len(bucket["employers"]),
                "agency_count": len(bucket["agencies"]),
            }
        )

    def _window(month_count: int) -> dict[str, Any]:
        selected = months[: min(month_count, len(months))]
        return {
            "opportunity_count": sum(int(item["opportunity_count"]) for item in selected),
            "monthly_deduction_value": round(
                sum(float(item["monthly_deduction_value"]) for item in selected), 2
            ),
        }

    peak = max(
        months,
        key=lambda item: (float(item["monthly_deduction_value"]), int(item["opportunity_count"])),
        default=None,
    )
    scheduled_count = sum(int(item["opportunity_count"]) for item in months)
    scheduled_value = round(sum(float(item["monthly_deduction_value"]) for item in months), 2)

    return {
        "as_of": today.isoformat(),
        "horizon_months": horizon_months,
        "summary": {
            "book_now_count": book_now_count,
            "book_now_value": round(book_now_value, 2),
            "book_now_client_count": len(book_now_clients),
            "scheduled_count": scheduled_count,
            "scheduled_value": scheduled_value,
            "scheduled_client_count": len(future_clients),
            "next_3_months": _window(3),
            "next_6_months": _window(6),
            "next_12_months": _window(12),
            "excluded_quality_count": excluded_quality_count,
            "excluded_quality_value": round(excluded_quality_value, 2),
            "unscheduled_count": unscheduled_count,
            "unscheduled_value": round(unscheduled_value, 2),
            "later_known_count": later_count,
            "later_known_value": round(later_value, 2),
            "missing_employer_client_count": len(missing_employer_clients),
            "peak_month": peak["month"] if peak and peak["opportunity_count"] else None,
            "peak_month_value": float(peak["monthly_deduction_value"]) if peak and peak["opportunity_count"] else 0.0,
        },
        "months": months,
        "top_employers": _finalize_concentration(employers),
        "top_agencies": _finalize_concentration(agencies),
    }
