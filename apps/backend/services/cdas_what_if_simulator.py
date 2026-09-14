from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from math import isfinite
from typing import Any


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


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


def calculate_monthly_installment(
    *,
    proposed_amount: float,
    term_months: int,
    annual_interest_rate: float,
) -> float:
    """Return an amortised monthly payment for a simple what-if scenario."""
    if proposed_amount <= 0:
        raise ValueError("Proposed amount must be greater than zero")
    if term_months <= 0:
        raise ValueError("Term months must be greater than zero")
    if annual_interest_rate < 0:
        raise ValueError("Annual interest rate cannot be negative")

    monthly_rate = (annual_interest_rate / 100.0) / 12.0
    if monthly_rate == 0:
        return round(proposed_amount / term_months, 2)

    factor = (1 + monthly_rate) ** term_months
    payment = proposed_amount * monthly_rate * factor / (factor - 1)
    return round(payment, 2)


def _current_capacity(snapshot: dict[str, Any]) -> float | None:
    capacity = snapshot.get("capacity") or {}
    for key in (
        "assessed_available_amount",
        "max_available_after_selected_deductions",
        "max_available_deduction_amount",
    ):
        value = _as_float(capacity.get(key))
        if value is not None:
            return round(value, 2)
    return None


def _future_release_windows(snapshot: dict[str, Any], *, today: date) -> list[dict[str, Any]]:
    grouped: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in snapshot.get("deductions") or []:
        booking_date = _as_date(row.get("booking_open_date"))
        deduction_amount = _as_float(row.get("deduction_amount"))
        if not booking_date or booking_date <= today or not deduction_amount or deduction_amount <= 0:
            continue
        if bool(row.get("excluded_from_booking")):
            continue
        if row.get("is_active") is False:
            continue
        status = str(row.get("booking_status") or "").upper()
        if status in {"DATA_CONFLICT", "DATA_INCOMPLETE", "NOT_ACTIVE"}:
            continue
        grouped[booking_date].append(row)

    windows: list[dict[str, Any]] = []
    cumulative = 0.0
    for booking_date in sorted(grouped):
        rows = grouped[booking_date]
        released = round(sum(float(row.get("deduction_amount") or 0) for row in rows), 2)
        cumulative = round(cumulative + released, 2)
        windows.append(
            {
                "booking_date": booking_date.isoformat(),
                "released_monthly_deduction": released,
                "cumulative_release": cumulative,
                "deductions": [
                    {
                        "item_code": row.get("item_code"),
                        "agency_name": row.get("agency_name"),
                        "reference_no": row.get("reference_no"),
                        "deduction_amount": round(float(row.get("deduction_amount") or 0), 2),
                        "expiry_date": _as_date(row.get("expiry_date")).isoformat()
                        if _as_date(row.get("expiry_date"))
                        else None,
                    }
                    for row in rows
                ],
            }
        )
    return windows


def simulate_what_if(
    *,
    opportunity: dict[str, Any],
    today: date,
    proposed_installment: float | None = None,
    proposed_amount: float | None = None,
    term_months: int | None = None,
    annual_interest_rate: float | None = None,
) -> dict[str, Any]:
    """Simulate a proposed deduction against one saved CDAS opportunity.

    This function is intentionally read-only. Future capacity is an estimate based
    only on valid saved deduction booking windows; it never rewrites the archived
    CDAS analysis or the real booking opportunity.
    """
    snapshot = opportunity.get("analysis_snapshot") or {}

    direct_installment = _as_float(proposed_installment)
    amount = _as_float(proposed_amount)
    rate = _as_float(annual_interest_rate)

    if direct_installment is not None:
        if direct_installment <= 0:
            raise ValueError("Proposed installment must be greater than zero")
        installment = round(direct_installment, 2)
        calculation_method = "DIRECT_INSTALLMENT"
    else:
        if amount is None or term_months is None or rate is None:
            raise ValueError(
                "Provide a proposed installment, or provide proposed amount, term months and annual interest rate"
            )
        installment = calculate_monthly_installment(
            proposed_amount=amount,
            term_months=term_months,
            annual_interest_rate=rate,
        )
        calculation_method = "AMORTIZED_PAYMENT"

    current_capacity = _current_capacity(snapshot)
    decision = str(snapshot.get("decision") or "").upper() or None
    quality_issue_count = int(snapshot.get("data_quality_issue_count") or 0)
    warnings: list[str] = []

    if decision == "REVIEW_REQUIRED":
        warnings.append("The saved CDAS analysis requires review before any booking decision is relied on.")
    if quality_issue_count:
        warnings.append(
            f"The saved CDAS analysis has {quality_issue_count} data-quality issue(s); future capacity is indicative only."
        )

    release_windows = _future_release_windows(snapshot, today=today)
    earliest_fit_date: str | None = None
    earliest_fit_capacity: float | None = None

    if current_capacity is None:
        status = "CAPACITY_UNKNOWN"
        fits_now = False
        remaining_capacity = None
        shortfall = None
        warnings.append("Current CDAS available deduction capacity is not present in the saved analysis.")
    else:
        effective_capacity = max(0.0, current_capacity)
        remaining_capacity = round(current_capacity - installment, 2)
        shortfall = round(max(0.0, installment - effective_capacity), 2)
        fits_now = installment <= effective_capacity

        if fits_now:
            status = "FITS_NOW"
        else:
            for window in release_windows:
                projected = round(effective_capacity + float(window["cumulative_release"]), 2)
                if installment <= projected:
                    earliest_fit_date = str(window["booking_date"])
                    earliest_fit_capacity = projected
                    break
            status = "FITS_AFTER_RELEASE" if earliest_fit_date else "EXCEEDS_KNOWN_CAPACITY"

    if decision == "REVIEW_REQUIRED" or quality_issue_count > 0:
        confidence = "REVIEW_REQUIRED"
    elif current_capacity is None:
        confidence = "LOW"
    elif earliest_fit_date:
        confidence = "INDICATIVE"
    else:
        confidence = "HIGH"

    projection_note = (
        "Future capacity is estimated from saved, valid deduction booking windows and should be re-analysed from fresh CDAS data before booking."
        if release_windows
        else "No future valid deduction release windows were found in the saved analysis."
    )

    return {
        "as_of": today.isoformat(),
        "opportunity_id": str(opportunity.get("id") or ""),
        "client_name": opportunity.get("client_name"),
        "client_reference": opportunity.get("client_reference"),
        "agency_name": opportunity.get("opportunity_agency_name"),
        "decision": decision,
        "data_quality_issue_count": quality_issue_count,
        "calculation_method": calculation_method,
        "scenario": {
            "proposed_installment": installment,
            "proposed_amount": amount,
            "term_months": term_months,
            "annual_interest_rate": rate,
        },
        "current_capacity": current_capacity,
        "fits_now": fits_now,
        "remaining_capacity": remaining_capacity,
        "shortfall": shortfall,
        "status": status,
        "requires_waiting_for_release": status == "FITS_AFTER_RELEASE",
        "earliest_fit_date": earliest_fit_date,
        "earliest_fit_capacity": earliest_fit_capacity,
        "confidence": confidence,
        "release_windows": release_windows,
        "warnings": warnings,
        "projection_note": projection_note,
    }
