from __future__ import annotations

from collections import Counter
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


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _employer_name(profile: dict[str, Any]) -> str | None:
    value = str(profile.get("employer") or "").strip()
    return value or None


def build_employer_intelligence(
    client_profiles: Iterable[dict[str, Any]],
    *,
    today: date,
) -> dict[str, Any]:
    """Aggregate employer-level intelligence from each exact client's latest CDAS profile."""
    day_30 = today + timedelta(days=30)
    day_90 = today + timedelta(days=90)
    employers: dict[str, dict[str, Any]] = {}
    missing_employer_clients = 0

    for profile in client_profiles:
        employer_name = _employer_name(profile)
        if not employer_name:
            missing_employer_clients += 1
            continue

        key = employer_name.casefold()
        entry = employers.setdefault(
            key,
            {
                "employer_name": employer_name,
                "client_count": 0,
                "active_deduction_count": 0,
                "active_monthly_value": 0.0,
                "own_monthly_value": 0.0,
                "competitor_monthly_value": 0.0,
                "book_now_count": 0,
                "book_now_value": 0.0,
                "next_30_days_count": 0,
                "next_30_days_value": 0.0,
                "next_90_days_count": 0,
                "next_90_days_value": 0.0,
                "earliest_competitor_booking_date": None,
                "capacity_known_count": 0,
                "available_capacity_total": 0.0,
                "no_headroom_count": 0,
                "data_quality_client_count": 0,
                "data_quality_issue_count": 0,
                "decision_counts": Counter(),
                "competitor_agencies": Counter(),
            },
        )

        entry["client_count"] += 1
        decision = str(profile.get("decision") or "UNKNOWN").upper()
        entry["decision_counts"][decision] += 1

        issue_count = int(profile.get("data_quality_issue_count") or 0)
        if issue_count:
            entry["data_quality_client_count"] += 1
            entry["data_quality_issue_count"] += issue_count

        capacity = profile.get("assessed_available_amount")
        if capacity is not None:
            amount = _money(capacity)
            entry["capacity_known_count"] += 1
            entry["available_capacity_total"] += max(0.0, amount)
            if amount <= 0:
                entry["no_headroom_count"] += 1

        for row in profile.get("current_deductions") or []:
            if not bool(row.get("reported_active")):
                continue

            amount = max(0.0, _money(row.get("deduction_amount")))
            entry["active_deduction_count"] += 1
            entry["active_monthly_value"] += amount

            if bool(row.get("is_own_booking")):
                entry["own_monthly_value"] += amount
                continue

            entry["competitor_monthly_value"] += amount
            agency = str(row.get("agency_name") or "Unknown agency").strip() or "Unknown agency"
            entry["competitor_agencies"][agency] += 1

            excluded = bool(row.get("excluded_from_booking"))
            quality_status = str(row.get("data_quality_status") or "OK").upper()
            if excluded or quality_status != "OK":
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

    items: list[dict[str, Any]] = []
    for entry in employers.values():
        client_count = int(entry["client_count"])
        active_monthly_value = round(float(entry["active_monthly_value"]), 2)
        competitor_monthly_value = round(float(entry["competitor_monthly_value"]), 2)
        capacity_known_count = int(entry["capacity_known_count"])
        available_capacity_total = round(float(entry["available_capacity_total"]), 2)
        quality_client_count = int(entry["data_quality_client_count"])
        top_competitors = [
            {"agency_name": name, "active_deduction_count": count}
            for name, count in entry["competitor_agencies"].most_common(5)
        ]
        items.append(
            {
                "employer_name": entry["employer_name"],
                "client_count": client_count,
                "active_deduction_count": int(entry["active_deduction_count"]),
                "active_monthly_value": active_monthly_value,
                "average_monthly_deductions_per_client": round(active_monthly_value / client_count, 2) if client_count else 0.0,
                "own_monthly_value": round(float(entry["own_monthly_value"]), 2),
                "competitor_monthly_value": competitor_monthly_value,
                "competitor_share_percent": round((competitor_monthly_value / active_monthly_value) * 100, 2) if active_monthly_value else 0.0,
                "book_now_count": int(entry["book_now_count"]),
                "book_now_value": round(float(entry["book_now_value"]), 2),
                "next_30_days_count": int(entry["next_30_days_count"]),
                "next_30_days_value": round(float(entry["next_30_days_value"]), 2),
                "next_90_days_count": int(entry["next_90_days_count"]),
                "next_90_days_value": round(float(entry["next_90_days_value"]), 2),
                "earliest_competitor_booking_date": entry["earliest_competitor_booking_date"].isoformat() if entry["earliest_competitor_booking_date"] else None,
                "capacity_known_count": capacity_known_count,
                "available_capacity_total": available_capacity_total,
                "average_available_capacity": round(available_capacity_total / capacity_known_count, 2) if capacity_known_count else 0.0,
                "no_headroom_count": int(entry["no_headroom_count"]),
                "data_quality_client_count": quality_client_count,
                "data_quality_issue_count": int(entry["data_quality_issue_count"]),
                "data_quality_client_percent": round((quality_client_count / client_count) * 100, 2) if client_count else 0.0,
                "decision_counts": dict(entry["decision_counts"]),
                "top_competitor_agencies": top_competitors,
            }
        )

    items.sort(
        key=lambda item: (
            -float(item["book_now_value"]),
            -float(item["next_90_days_value"]),
            -float(item["competitor_monthly_value"]),
            str(item["employer_name"]).casefold(),
        )
    )

    return {
        "as_of": today.isoformat(),
        "summary": {
            "employer_count": len(items),
            "client_count": sum(int(item["client_count"]) for item in items),
            "missing_employer_clients": missing_employer_clients,
            "active_monthly_value": round(sum(float(item["active_monthly_value"]) for item in items), 2),
            "competitor_monthly_value": round(sum(float(item["competitor_monthly_value"]) for item in items), 2),
            "book_now_count": sum(int(item["book_now_count"]) for item in items),
            "book_now_value": round(sum(float(item["book_now_value"]) for item in items), 2),
            "next_30_days_value": round(sum(float(item["next_30_days_value"]) for item in items), 2),
            "next_90_days_value": round(sum(float(item["next_90_days_value"]) for item in items), 2),
            "available_capacity_total": round(sum(float(item["available_capacity_total"]) for item in items), 2),
            "data_quality_client_count": sum(int(item["data_quality_client_count"]) for item in items),
        },
        "items": items,
        "total": len(items),
    }
