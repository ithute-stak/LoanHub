from __future__ import annotations


def present_value_from_payment(
    *,
    monthly_payment: float,
    term_months: int,
    annual_interest_rate: float,
) -> float:
    """Return the financed balance supported by a fixed monthly payment."""
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


def calculate_reference_max_principal(
    *,
    monthly_capacity: float,
    term_months: int,
    annual_interest_rate: float,
    monthly_service_fee: float = 0.0,
    insurance_percent: float = 0.0,
) -> dict:
    """Reference-only arithmetic from staff-entered values.

    This does not determine eligibility, approve lending, or read borrower/CDAS data.
    """
    if monthly_capacity < 0:
        raise ValueError("Monthly capacity cannot be negative")
    if term_months <= 0:
        raise ValueError("Term months must be greater than zero")
    if annual_interest_rate < 0:
        raise ValueError("Annual interest rate cannot be negative")
    if monthly_service_fee < 0:
        raise ValueError("Monthly service fee cannot be negative")
    if insurance_percent < 0:
        raise ValueError("Insurance percent cannot be negative")

    installment_budget = round(max(0.0, monthly_capacity - monthly_service_fee), 2)
    if installment_budget <= 0:
        financed_balance = 0.0
        max_principal = 0.0
        insurance_amount = 0.0
        status = "NO_CAPACITY"
    else:
        financed_balance = present_value_from_payment(
            monthly_payment=installment_budget,
            term_months=term_months,
            annual_interest_rate=annual_interest_rate,
        )
        insurance_multiplier = 1 + (insurance_percent / 100.0)
        max_principal = round(financed_balance / insurance_multiplier, 2)
        insurance_amount = round(financed_balance - max_principal, 2)
        status = "CALCULATED"

    return {
        "status": status,
        "inputs": {
            "monthly_capacity": round(float(monthly_capacity), 2),
            "term_months": term_months,
            "annual_interest_rate": round(float(annual_interest_rate), 4),
            "monthly_service_fee": round(float(monthly_service_fee), 2),
            "insurance_percent": round(float(insurance_percent), 4),
        },
        "installment_budget": installment_budget,
        "max_financed_balance": financed_balance,
        "insurance_amount": insurance_amount,
        "max_principal": max_principal,
        "projected_monthly_total": round(installment_budget + monthly_service_fee, 2),
        "calculation_note": (
            "Reference calculation only. Staff entered the monthly capacity manually. "
            "The result is not a credit decision, approval, eligibility determination, or borrower-specific limit."
        ),
    }
