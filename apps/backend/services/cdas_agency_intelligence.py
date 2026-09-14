from __future__ import annotations

from collections import defaultdict
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


def _agency_name(row: dict[str, Any]) -> str:
    value = str(row.get("agency_name") or "").strip()
    return value or "Unknown agency"


def build_agency_intelligence(
    client_profiles: Iterable[dict[str, Any]],
    *,
    today: date,
) -> dict[str, Any]:
    """Aggregate agency-level intelligence from each client's latest CDAS deductions."""
    day_30 = today + timedelta(days=30)
    day_90 = today + timedelta(days=90)
    agencies: dict[str, dict[str, Any]] = {}
    total_clients: set[str] = set()

    for profile in client_profiles:
        client_key = str(profile.get("client_key") or "").strip()
        if client_key:
            total_clients.add(client_key)
        for row in profile.get("current_deductions") or []:
            if not bool(row.get("reported_active")):
                continue

            name = _agency_name(row)
            key = name.casefold()
            entry = agencies.setdefault(
                key,
                {
                    "agency_name": name,
                    "item_codes": set(),
                    "client_keys": set(),
                    "active_deduction_count": 0,
                    "active_monthly_value": 0.0,
                    "own_booking_count": 0,
                    "own_monthly_value": 0.0,
                    "competitor_booking_count": 0,
                    "competitor_monthly_value": 0.0,
                    "book_now_count": 0,
                    "book_now_value": 0.0,
                    "next_30_days_count": 0,
                    "next_30_days_value": 0.0,
                    "next_90_days_count": 0,
                    "next_90_days_value": 0.0,
                    "earliest_competitor_booking_date": None,
                    "data_quality_issue_count": 0,
                },
            )

            item_code = str(row.get("item_code") or "").strip()
            if item_code:
                entry["item_codes"].add(item_code)
            if client_key:
                entry["client_keys"].add(client_key)

            amount = max(0.0, float(row.get("deduction_amount") or 0))
            entry["active_deduction_count"] += 1
            entry["active_monthly_value"] += amount

            is_own = bool(row.get("is_own_booking"))
            if is_own:
                entry["own_booking_count"] += 1
                entry["own_monthly_value"] += amount
                continue

            entry["competitor_booking_count"] += 1
            entry["competitor_monthly_value"] += amount

            excluded = bool(row.get("excluded_from_booking"))
            quality_status = str(row.get("data_quality_status") or "OK").upper()
            if excluded or quality_status != "OK":
                entry["data_quality_issue_count"] += 1
                continue

            booking_date = _as_date(row.get("booking_open_date"))
            booking_status = str(row.get("booking_status") or "").upper()
            if booking_status == "BOOK_NOW" or (booking_date and booking_date <= today):
                entry["book_now_count"] += 1
                entry["book_now_value"] += amount

            if booking_date and today <= booking_date <= day_30:
                entry["next_30_days_count"] += 1
                entry["next_30_days_value"] += amount
            if booking_date and today <= booking_date <= day_90:
                entry["next_90_days_count"] += 1
                entry["next_90_days_value"] += amount

            if booking_date:
                current = entry["earliest_competitor_booking_date"]
                if current is None or booking_date < current:
                    entry["earliest_competitor_booking_date"] = booking_date

    total_competitor_value = sum(float(entry["competitor_monthly_value"]) for entry in agencies.values())
    items: list[dict[str, Any]] = []
    for entry in agencies.values():
        active_count = int(entry["active_deduction_count"])
        competitor_value = round(float(entry["competitor_monthly_value"]), 2)
        items.append(
            {
                "agency_name": entry["agency_name"],
                "item_codes": sorted(entry["item_codes"]),
                "client_count": len(entry["client_keys"]),
                "active_deduction_count": active_count,
                "active_monthly_value": round(float(entry["active_monthly_value"]), 2),
                "average_deduction_amount": round(float(entry["active_monthly_value"]) / active_count, 2) if active_count else 0.0,
                "own_booking_count": int(entry["own_booking_count"]),
                "own_monthly_value": round(float(entry["own_monthly_value"]), 2),
                "competitor_booking_count": int(entry["competitor_booking_count"]),
                "competitor_monthly_value": competitor_value,
                "competitor_value_share_percent": round((competitor_value / total_competitor_value) * 100, 2) if total_competitor_value else 0.0,
                "book_now_count": int(entry["book_now_count"]),
                "book_now_value": round(float(entry["book_now_value"]), 2),
                "next_30_days_count": int(entry["next_30_days_count"]),
                "next_30_days_value": round(float(entry["next_30_days_value"]), 2),
                "next_90_days_count": int(entry["next_90_days_count"]),
                "next_90_days_value": round(float(entry["next_90_days_value"]), 2),
                "earliest_competitor_booking_date": entry["earliest_competitor_booking_date"].isoformat() if entry["earliest_competitor_booking_date"] else None,
                "data_quality_issue_count": int(entry["data_quality_issue_count"]),
            }
        )

    items.sort(
        key=lambda item: (
            -float(item["competitor_monthly_value"]),
            -int(item["competitor_booking_count"]),
            str(item["agency_name"]).casefold(),
        )
    )

    summary = {
        "agency_count": len(items),
        "client_count": len(total_clients),
        "active_deduction_count": sum(int(item["active_deduction_count"]) for item in items),
        "active_monthly_value": round(sum(float(item["active_monthly_value"]) for item in items), 2),
        "own_monthly_value": round(sum(float(item["own_monthly_value"]) for item in items), 2),
        "competitor_monthly_value": round(sum(float(item["competitor_monthly_value"]) for item in items), 2),
        "book_now_count": sum(int(item["book_now_count"]) for item in items),
        "book_now_value": round(sum(float(item["book_now_value"]) for item in items), 2),
        "next_30_days_count": sum(int(item["next_30_days_count"]) for item in items),
        "next_30_days_value": round(sum(float(item["next_30_days_value"]) for item in items), 2),
        "next_90_days_count": sum(int(item["next_90_days_count"]) for item in items),
        "next_90_days_value": round(sum(float(item["next_90_days_value"]) for item in items), 2),
    }

    return {
        "as_of": today.isoformat(),
        "summary": summary,
        "items": items,
        "total": len(items),
    }
