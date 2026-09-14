from __future__ import annotations

from datetime import date
from math import ceil


BOOKING_CAPACITY_THRESHOLD = 1.0


def apply_capacity_booking_policy(
    analysis: dict,
    *,
    as_of: date,
    amount_owing: float | None = None,
) -> dict:
    """Apply the business rule that positive CDAS capacity can open booking now.

    The assessed amount uses the consolidation-after-selected-deductions value when
    CDAS supplies it; otherwise it uses the current Max Available Deduction Amount.
    A value must be strictly greater than M1.00 to allow capacity-based booking.
    """
    capacity = analysis.setdefault("capacity", {})
    current = capacity.get("max_available_deduction_amount")
    after_selected = capacity.get("max_available_after_selected_deductions")
    assessed = after_selected if after_selected is not None else current
    assessed_amount = round(float(assessed), 2) if assessed is not None else None
    booking_allowed = bool(
        assessed_amount is not None and assessed_amount > BOOKING_CAPACITY_THRESHOLD
    )

    capacity["assessed_available_amount"] = assessed_amount
    capacity["booking_threshold_amount"] = BOOKING_CAPACITY_THRESHOLD
    capacity["booking_allowed"] = booking_allowed

    owing = round(float(amount_owing), 2) if amount_owing is not None else None
    months_required = None
    if booking_allowed and owing is not None and owing > 0:
        months_required = max(1, ceil(owing / assessed_amount))

    analysis["booking_term"] = {
        "amount_owing": owing,
        "monthly_available_deduction": assessed_amount,
        "months_required": months_required,
        "calculation": (
            "ceil(amount_owing / monthly_available_deduction)"
            if months_required is not None
            else None
        ),
    }

    if analysis.get("decision") == "ALREADY_BOOKED" or not booking_allowed:
        return analysis

    analysis["decision"] = "BOOK_NOW"
    analysis["next_possible_booking_date"] = date(as_of.year, as_of.month, 1).isoformat()
    if months_required is not None:
        analysis["decision_message"] = (
            f"CDAS reports {assessed_amount:,.2f} maloti of monthly deduction capacity, "
            f"which is above the M{BOOKING_CAPACITY_THRESHOLD:,.2f} booking threshold. "
            f"The client can be booked now. An amount owing of M{owing:,.2f} requires "
            f"{months_required} month(s) when using up to M{assessed_amount:,.2f} per month."
        )
    else:
        analysis["decision_message"] = (
            f"CDAS reports {assessed_amount:,.2f} maloti of monthly deduction capacity, "
            f"which is above the M{BOOKING_CAPACITY_THRESHOLD:,.2f} booking threshold. "
            "The client can be booked now. Enter the amount the client is owing so "
            "LoanHub can calculate the minimum number of booking months."
        )
    return analysis
