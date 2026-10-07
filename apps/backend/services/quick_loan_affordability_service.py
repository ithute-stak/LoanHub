from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from database.models.borrower import Borrower
from database.models.origination import OriginationPolicy
from services.polyglot_runtime_service import (
    java_underwriting_rules,
    record_parity_mismatch,
    rust_affordability_assessment,
    workload_routing_mode,
)

MONEY = Decimal("0.01")
PERCENT = Decimal("0.001")


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _percent(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(PERCENT, rounding=ROUND_HALF_UP)


def quick_loan_affordability(
    *,
    borrower: Borrower,
    policy: OriginationPolicy,
    proposed_installment: Decimal,
    bureau_monthly_commitments: Decimal | None = None,
    live_cdas_affordability: Decimal | None = None,
) -> dict[str, Any]:
    """Assess a marketplace/quick-loan offer before the lender approves it.

    This uses the borrower's durable shared profile and the lender company's
    configured affordability policy. It never approves a loan by itself.
    """
    base_income = (
        _money(borrower.net_monthly_income)
        if borrower.net_monthly_income is not None
        else _money(borrower.monthly_income)
    )
    other_income = _money(borrower.other_monthly_income)
    income = _money(base_income + other_income)
    living = _money(borrower.monthly_living_expenses)
    profile_debt = _money(borrower.monthly_debt_repayments)
    bureau_debt = _money(bureau_monthly_commitments) if bureau_monthly_commitments is not None else Decimal("0.00")
    debt = max(profile_debt, bureau_debt)
    dependants = int(borrower.dependants or 0)
    dependant_allowance = _money(policy.dependant_allowance)
    dependant_total = _money(Decimal(dependants) * dependant_allowance)
    buffer_amount = _money(policy.living_expense_buffer)
    installment = _money(proposed_installment)

    committed_before_new_loan = _money(living + debt + dependant_total + buffer_amount)
    disposable_before_new_loan = _money(income - committed_before_new_loan)

    disposable_limit = _money(
        max(disposable_before_new_loan, Decimal("0"))
        * Decimal(policy.disposable_income_usage_percent or 0)
        / Decimal("100")
    )
    dti_limit = _money(
        max(
            income * Decimal(policy.max_dti_percent or 0) / Decimal("100") - debt,
            Decimal("0"),
        )
    )
    installment_income_limit = _money(
        income
        * Decimal(policy.max_installment_income_percent or 0)
        / Decimal("100")
    )
    internal_maximum_affordable_installment = _money(
        min(disposable_limit, dti_limit, installment_income_limit)
    )
    maximum_affordable_installment = (
        _money(min(internal_maximum_affordable_installment, _money(live_cdas_affordability)))
        if live_cdas_affordability is not None
        else internal_maximum_affordable_installment
    )

    after_installment = _money(disposable_before_new_loan - installment)
    dti = (
        _percent((debt + installment) * Decimal("100") / income)
        if income > 0
        else Decimal("100.000")
    )
    headroom = _money(maximum_affordable_installment - installment)

    reasons: list[dict[str, str]] = []
    passed = True

    if income <= 0:
        passed = False
        reasons.append(
            {
                "severity": "error",
                "code": "income_missing",
                "message": "Monthly income is missing or zero.",
            }
        )
    elif income < _money(policy.min_verified_net_income):
        passed = False
        reasons.append(
            {
                "severity": "error",
                "code": "income_below_minimum",
                "message": "Monthly income is below the lender's configured minimum.",
            }
        )
    else:
        reasons.append(
            {
                "severity": "pass",
                "code": "income_ok",
                "message": "Monthly income meets the lender's configured minimum.",
            }
        )

    if installment > maximum_affordable_installment:
        passed = False
        reasons.append(
            {
                "severity": "error",
                "code": "installment_above_limit",
                "message": "The proposed installment exceeds the calculated affordability limit.",
            }
        )
    else:
        reasons.append(
            {
                "severity": "pass",
                "code": "installment_within_limit",
                "message": "The proposed installment is within the calculated affordability limit.",
            }
        )

    minimum_after_installment = _money(policy.min_disposable_after_installment)
    if after_installment < minimum_after_installment:
        passed = False
        reasons.append(
            {
                "severity": "error",
                "code": "disposable_income_too_low",
                "message": "Disposable income after the proposed installment is below the lender's minimum.",
            }
        )

    result = {
        "decision": "pass" if passed else "fail",
        "passed": passed,
        "input_source": "composite_external_affordability",
        "external_sources": {
            "bureau": {
                "used": bureau_monthly_commitments is not None,
                "monthly_commitments": str(bureau_debt),
            },
            "cdas": {
                "used": live_cdas_affordability is not None,
                "live_affordability": str(_money(live_cdas_affordability)) if live_cdas_affordability is not None else None,
            },
        },
        "policy_id": str(policy.id),
        "policy_version": int(policy.version or 1),
        "monthly_income": str(income),
        "base_income": str(base_income),
        "other_income": str(other_income),
        "living_expenses": str(living),
        "existing_debt_repayments": str(debt),
        "profile_debt_repayments": str(profile_debt),
        "bureau_monthly_commitments": str(bureau_debt),
        "dependants": dependants,
        "dependant_allowance_total": str(dependant_total),
        "configured_buffer": str(buffer_amount),
        "disposable_before_new_loan": str(disposable_before_new_loan),
        "proposed_installment": str(installment),
        "internal_maximum_affordable_installment": str(internal_maximum_affordable_installment),
        "maximum_affordable_installment": str(maximum_affordable_installment),
        "affordability_headroom": str(headroom),
        "disposable_after_installment": str(after_installment),
        "dti_percent": str(dti),
        "limits": {
            "disposable_income_limit": str(disposable_limit),
            "dti_limit": str(dti_limit),
            "installment_income_limit": str(installment_income_limit),
            "minimum_disposable_after_installment": str(minimum_after_installment),
        },
        "reasons": reasons,
    }

    routing_mode = workload_routing_mode("rust_affordability")
    rust_value = None
    if routing_mode != "off":
        rust_value = rust_affordability_assessment(
            base_income=str(base_income),
            other_income=str(other_income),
            living_expenses=str(living),
            existing_debt_repayments=str(debt),
            dependants=dependants,
            dependant_allowance=str(dependant_allowance),
            living_expense_buffer=str(buffer_amount),
            proposed_installment=str(installment),
            disposable_income_usage_percent=str(policy.disposable_income_usage_percent or 0),
            max_dti_percent=str(policy.max_dti_percent or 0),
            max_installment_income_percent=str(policy.max_installment_income_percent or 0),
            min_verified_net_income=str(policy.min_verified_net_income or 0),
            min_disposable_after_installment=str(minimum_after_installment),
        )

    parity_fields = {
        "passed": passed,
        "monthly_income": str(income),
        "base_income": str(base_income),
        "other_income": str(other_income),
        "living_expenses": str(living),
        "existing_debt_repayments": str(debt),
        "dependant_allowance_total": str(dependant_total),
        "configured_buffer": str(buffer_amount),
        "disposable_before_new_loan": str(disposable_before_new_loan),
        "proposed_installment": str(installment),
        "maximum_affordable_installment": str(maximum_affordable_installment),
        "affordability_headroom": str(headroom),
        "disposable_after_installment": str(after_installment),
        "dti_percent": str(dti),
        "disposable_income_limit": str(disposable_limit),
        "dti_limit": str(dti_limit),
        "installment_income_limit": str(installment_income_limit),
        "minimum_disposable_after_installment": str(minimum_after_installment),
        "income_missing": income <= 0,
        "income_below_minimum": income > 0 and income < _money(policy.min_verified_net_income),
        "installment_above_limit": installment > maximum_affordable_installment,
        "disposable_income_too_low": after_installment < minimum_after_installment,
    }
    rust_parity = bool(
        rust_value is not None
        and all(rust_value.get(key) == value for key, value in parity_fields.items())
    )
    if rust_value is not None and not rust_parity:
        record_parity_mismatch("rust_compute")

    if rust_parity and routing_mode == "prefer-worker":
        for key in (
            "monthly_income",
            "base_income",
            "other_income",
            "living_expenses",
            "existing_debt_repayments",
            "dependant_allowance_total",
            "configured_buffer",
            "disposable_before_new_loan",
            "proposed_installment",
            "maximum_affordable_installment",
            "affordability_headroom",
            "disposable_after_installment",
            "dti_percent",
        ):
            result[key] = rust_value[key]
        result["limits"] = {
            "disposable_income_limit": rust_value["disposable_income_limit"],
            "dti_limit": rust_value["dti_limit"],
            "installment_income_limit": rust_value["installment_income_limit"],
            "minimum_disposable_after_installment": rust_value["minimum_disposable_after_installment"],
        }

    java_mode = workload_routing_mode("java_underwriting_rules")
    java_value = None
    if java_mode != "off":
        java_value = java_underwriting_rules(
            monthly_income=str(income),
            min_verified_net_income=str(_money(policy.min_verified_net_income)),
            proposed_installment=str(installment),
            maximum_affordable_installment=str(maximum_affordable_installment),
            disposable_after_installment=str(after_installment),
            min_disposable_after_installment=str(minimum_after_installment),
        )

    java_parity = bool(
        java_value is not None
        and java_value.get("passed") is passed
        and java_value.get("decision") == result["decision"]
        and java_value.get("reasons") == reasons
    )
    if java_value is not None and not java_parity:
        record_parity_mismatch("java_worker")
    if java_parity and java_mode == "prefer-worker":
        result["decision"] = java_value["decision"]
        result["passed"] = java_value["passed"]
        result["reasons"] = java_value["reasons"]

    result["compute_runtime"] = {
        "rust_routing_mode": routing_mode,
        "rust_available": rust_value is not None,
        "rust_parity": "match" if rust_parity else ("mismatch" if rust_value is not None else "unavailable"),
        "rust_used": bool(rust_parity and routing_mode == "prefer-worker"),
        "java_routing_mode": java_mode,
        "java_available": java_value is not None,
        "java_parity": "match" if java_parity else ("mismatch" if java_value is not None else "unavailable"),
        "java_used": bool(java_parity and java_mode == "prefer-worker"),
        "python_authority": True,
    }
    return result
