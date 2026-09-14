from __future__ import annotations

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


def _available_capacity(snapshot: dict[str, Any]) -> float | None:
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


def present_value_from_payment(
    *,
    monthly_payment: float,
    term_months: int,
    annual_interest_rate: float,
) -> float:
    if monthly_payment < 0:
        raise ValueError("Monthly payment cannot be negative")
    if term_months <= 0:
        raise ValueError("Term months must be greater than zero")
    if annual_interest_rate < 0:
        raise ValueError("Annual interest rate cannot be negative")

    monthly_rate = (annual_interest_rate / 100.0) / 12.0
    if monthly_rate == 0:
        return round(monthly_payment * term_months, 2)

    factor = (1 - (1 + monthly_rate) ** (-term_months)) / monthly_rate
    return round(monthly_payment * factor, 2)


def calculate_max_loan_amount(
    *,
    opportunity: dict[str, Any],
    term_months: int,
    annual_interest_rate: float,
    monthly_service_fee: float = 0.0,
    insurance_percent: float = 0.0,
) -> dict[str, Any]:
    """Calculate the maximum principal that fits the saved CDAS monthly capacity."""
    if term_months <= 0:
        raise ValueError("Term months must be greater than zero")
    if annual_interest_rate < 0:
        raise ValueError("Annual interest rate cannot be negative")
    if monthly_service_fee < 0:
        raise ValueError("Monthly service fee cannot be negative")
    if insurance_percent < 0:
        raise ValueError("Insurance percent cannot be negative")

    snapshot = opportunity.get("analysis_snapshot") or {}
    current_capacity = _available_capacity(snapshot)
    decision = str(snapshot.get("decision") or "").upper() or None
    quality_issue_count = int(snapshot.get("data_quality_issue_count") or 0)
    warnings: list[str] = []

    if decision == "REVIEW_REQUIRED":
        warnings.append("The saved CDAS analysis requires review before this capacity is relied on.")
    if quality_issue_count:
        warnings.append(
            f"The saved CDAS analysis has {quality_issue_count} data-quality issue(s); recalculate after fresh CDAS review before booking."
        )

    if current_capacity is None:
        status = "CAPACITY_UNKNOWN"
        installment_budget = None
        max_financed_balance = None
        max_principal = None
        insurance_amount = None
        projected_monthly_total = None
        confidence = "LOW" if decision != "REVIEW_REQUIRED" and quality_issue_count == 0 else "REVIEW_REQUIRED"
        warnings.append("Current CDAS available deduction capacity is not present in the saved analysis.")
    else:
        usable_capacity = max(0.0, current_capacity)
        installment_budget = round(max(0.0, usable_capacity - monthly_service_fee), 2)

        if installment_budget <= 0:
            status = "NO_CAPACITY"
            max_financed_balance = 0.0
            max_principal = 0.0
            insurance_amount = 0.0
            projected_monthly_total = round(monthly_service_fee, 2)
        else:
            max_financed_balance = present_value_from_payment(
                monthly_payment=installment_budget,
                term_months=term_months,
                annual_interest_rate=annual_interest_rate,
            )
            insurance_multiplier = 1 + (insurance_percent / 100.0)
            max_principal = round(max_financed_balance / insurance_multiplier, 2)
            insurance_amount = round(max_financed_balance - max_principal, 2)
            projected_monthly_total = round(installment_budget + monthly_service_fee, 2)
            status = "CALCULATED"

        confidence = (
            "REVIEW_REQUIRED"
            if decision == "REVIEW_REQUIRED" or quality_issue_count > 0
            else "HIGH"
        )

    return {
        "opportunity_id": str(opportunity.get("id") or ""),
        "client_name": opportunity.get("client_name"),
        "client_reference": opportunity.get("client_reference"),
        "agency_name": opportunity.get("opportunity_agency_name"),
        "decision": decision,
        "data_quality_issue_count": quality_issue_count,
        "status": status,
        "confidence": confidence,
        "inputs": {
            "term_months": term_months,
            "annual_interest_rate": round(float(annual_interest_rate), 4),
            "monthly_service_fee": round(float(monthly_service_fee), 2),
            "insurance_percent": round(float(insurance_percent), 4),
        },
        "available_deduction_capacity": current_capacity,
        "installment_budget": installment_budget,
        "max_financed_balance": max_financed_balance,
        "insurance_amount": insurance_amount,
        "max_principal": max_principal,
        "projected_monthly_total": projected_monthly_total,
        "warnings": warnings,
        "calculation_note": (
            "Maximum principal is an affordability estimate from the saved CDAS monthly deduction capacity. "
            "It excludes taxes, once-off fees and product-specific rules not entered here, and fresh CDAS data must be checked before booking."
        ),
    }
