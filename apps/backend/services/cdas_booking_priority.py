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


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _urgency_component(booking_date: date | None, *, today: date) -> tuple[int, str, list[str]]:
    warnings: list[str] = []
    if booking_date is None:
        warnings.append("Booking date is missing; schedule this opportunity before relying on its priority score.")
        return 0, "Booking date missing", warnings

    delta = (booking_date - today).days
    if delta < 0:
        overdue = abs(delta)
        if overdue >= 30:
            return 50, f"Overdue by {overdue} days", warnings
        if overdue >= 14:
            return 48, f"Overdue by {overdue} days", warnings
        return 46, f"Overdue by {overdue} days", warnings
    if delta == 0:
        return 45, "Booking is due today", warnings
    if delta <= 3:
        return 42, f"Booking opens in {delta} day(s)", warnings
    if delta <= 7:
        return 38, f"Booking opens in {delta} days", warnings
    if delta <= 14:
        return 32, f"Booking opens in {delta} days", warnings
    if delta <= 30:
        return 25, f"Booking opens in {delta} days", warnings
    if delta <= 60:
        return 16, f"Booking opens in {delta} days", warnings
    if delta <= 90:
        return 10, f"Booking opens in {delta} days", warnings
    return 5, f"Booking opens in {delta} days", warnings


def _value_component(deduction_amount: float) -> tuple[int, str]:
    if deduction_amount >= 5000:
        return 20, "Very high monthly deduction opportunity"
    if deduction_amount >= 2500:
        return 17, "High monthly deduction opportunity"
    if deduction_amount >= 1000:
        return 13, "Meaningful monthly deduction opportunity"
    if deduction_amount >= 500:
        return 9, "Moderate monthly deduction opportunity"
    if deduction_amount > 0:
        return 5, "Small monthly deduction opportunity"
    return 0, "Deduction amount is not available"


def _readiness_component(snapshot: dict[str, Any], booking_date: date | None) -> tuple[int, str, list[str]]:
    warnings: list[str] = []
    decision = str(snapshot.get("decision") or "").upper()
    capacity = snapshot.get("capacity") or {}
    booking_allowed = bool(capacity.get("booking_allowed"))
    assessed = _as_float(capacity.get("assessed_available_amount"))
    if assessed is None:
        assessed = _as_float(capacity.get("max_available_after_selected_deductions"))
    if assessed is None:
        assessed = _as_float(capacity.get("max_available_deduction_amount"))

    if decision == "REVIEW_REQUIRED":
        warnings.append("CDAS analysis requires review before booking.")
        return 0, "Booking blocked by CDAS review", warnings
    if booking_allowed or decision == "BOOK_NOW":
        return 20, "CDAS says booking is allowed now", warnings
    if assessed is not None and assessed > 0:
        return 12, "Positive CDAS deduction capacity is available", warnings
    if booking_date is not None:
        return 8, "Booking date is known but immediate capacity is not confirmed", warnings

    warnings.append("Booking readiness cannot yet be confirmed from the saved analysis.")
    return 0, "Booking readiness is unknown", warnings


def _quality_component(snapshot: dict[str, Any]) -> tuple[int, str, list[str]]:
    warnings: list[str] = []
    issue_count = int(snapshot.get("data_quality_issue_count") or 0)
    if issue_count <= 0:
        return 10, "CDAS data passed quality checks", warnings
    if issue_count == 1:
        warnings.append("One CDAS data-quality issue reduces this opportunity's priority confidence.")
        return 4, "One CDAS data-quality issue", warnings
    warnings.append(f"{issue_count} CDAS data-quality issues reduce this opportunity's priority confidence.")
    return 0, f"{issue_count} CDAS data-quality issues", warnings


def _band(score: int, *, booked: bool) -> str:
    if booked:
        return "BOOKED"
    if score >= 85:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def score_booking_priority(item: dict[str, Any], *, today: date) -> dict[str, Any]:
    """Return an explainable 0-100 booking priority score for one opportunity."""
    state = str(item.get("state") or "UPCOMING").upper()
    booked = state == "BOOKED" or str(item.get("status") or "").lower() == "booked"
    booking_date = _as_date(item.get("booking_open_date"))
    deduction_amount = max(0.0, float(item.get("opportunity_deduction_amount") or 0))
    snapshot = item.get("analysis_snapshot") or {}

    if booked:
        return {
            "score": 0,
            "band": "BOOKED",
            "components": {"urgency": 0, "value": 0, "readiness": 0, "quality": 0},
            "reasons": ["Booking is already complete"],
            "warnings": [],
        }

    urgency, urgency_reason, urgency_warnings = _urgency_component(booking_date, today=today)
    value, value_reason = _value_component(deduction_amount)
    readiness, readiness_reason, readiness_warnings = _readiness_component(snapshot, booking_date)
    quality, quality_reason, quality_warnings = _quality_component(snapshot)

    score = max(0, min(100, urgency + value + readiness + quality))
    return {
        "score": score,
        "band": _band(score, booked=False),
        "components": {
            "urgency": urgency,
            "value": value,
            "readiness": readiness,
            "quality": quality,
        },
        "reasons": [urgency_reason, value_reason, readiness_reason, quality_reason],
        "warnings": urgency_warnings + readiness_warnings + quality_warnings,
    }


def _priority_item(item: dict[str, Any], *, today: date) -> dict[str, Any]:
    priority = score_booking_priority(item, today=today)
    snapshot = item.get("analysis_snapshot") or {}
    capacity = snapshot.get("capacity") or {}
    assessed = _as_float(capacity.get("assessed_available_amount"))
    if assessed is None:
        assessed = _as_float(capacity.get("max_available_after_selected_deductions"))
    if assessed is None:
        assessed = _as_float(capacity.get("max_available_deduction_amount"))

    booking_date = _as_date(item.get("booking_open_date"))
    return {
        "id": str(item.get("id") or ""),
        "client_name": item.get("client_name"),
        "client_reference": item.get("client_reference"),
        "agency_name": item.get("opportunity_agency_name"),
        "reference_no": item.get("opportunity_reference_no"),
        "deduction_amount": float(item.get("opportunity_deduction_amount") or 0),
        "booking_date": booking_date.isoformat() if booking_date else None,
        "expiry_date": _as_date(item.get("opportunity_expiry_date")).isoformat() if _as_date(item.get("opportunity_expiry_date")) else None,
        "state": str(item.get("state") or "UPCOMING").upper(),
        "days_from_today": (booking_date - today).days if booking_date else None,
        "decision": snapshot.get("decision"),
        "assessed_available_amount": assessed,
        "data_quality_issue_count": int(snapshot.get("data_quality_issue_count") or 0),
        "amount_owing": _as_float((snapshot.get("booking_term") or {}).get("amount_owing")),
        "booking_months": (snapshot.get("booking_term") or {}).get("months_required"),
        "priority_score": priority["score"],
        "priority_band": priority["band"],
        "priority_components": priority["components"],
        "priority_reasons": priority["reasons"],
        "priority_warnings": priority["warnings"],
    }


def build_booking_priority_queue(
    opportunities: Iterable[dict[str, Any]],
    *,
    today: date,
) -> dict[str, Any]:
    items = [_priority_item(item, today=today) for item in opportunities]
    items.sort(
        key=lambda item: (
            1 if item["priority_band"] == "BOOKED" else 0,
            -int(item["priority_score"]),
            str(item.get("booking_date") or "9999-12-31"),
            str(item.get("client_name") or item.get("client_reference") or ""),
        )
    )

    open_items = [item for item in items if item["priority_band"] != "BOOKED"]
    summary = {
        "critical": sum(1 for item in open_items if item["priority_band"] == "CRITICAL"),
        "high": sum(1 for item in open_items if item["priority_band"] == "HIGH"),
        "medium": sum(1 for item in open_items if item["priority_band"] == "MEDIUM"),
        "low": sum(1 for item in open_items if item["priority_band"] == "LOW"),
        "review_required": sum(1 for item in open_items if str(item.get("decision") or "").upper() == "REVIEW_REQUIRED"),
        "booked": sum(1 for item in items if item["priority_band"] == "BOOKED"),
        "open": len(open_items),
        "monthly_deduction_value": round(sum(float(item.get("deduction_amount") or 0) for item in open_items), 2),
    }

    return {
        "as_of": today.isoformat(),
        "summary": summary,
        "items": items,
        "total": len(items),
    }
