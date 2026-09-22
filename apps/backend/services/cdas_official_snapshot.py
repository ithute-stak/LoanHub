from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any


_ACTIVE_STATUS_VALUES = {5, "5", "active", "approved and active"}


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _amount(value: Any) -> float:
    if value is None or isinstance(value, bool):
        return 0.0
    try:
        if isinstance(value, str):
            value = value.replace("M", "").replace(",", "").strip()
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


def _is_active_status(value: Any) -> bool:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in _ACTIVE_STATUS_VALUES
    return value in _ACTIVE_STATUS_VALUES


def _stable_provider_rows(value: Any) -> list[dict[str, Any]]:
    rows = [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []
    return sorted(
        rows,
        key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), default=str),
    )


def _normalize_deduction(row: dict[str, Any], *, own: bool) -> dict[str, Any]:
    return {
        "deduction_id": _first(row, "DeductionID", "deductionId", "deduction_id"),
        "employee_no": _text(_first(row, "EmployeeNo", "employeeNo", "employee_no")),
        "item_code": _text(_first(row, "ItemCode", "itemCode", "item_code")),
        "reference_no": _text(_first(row, "ReferenceNo", "referenceNo", "reference_no")),
        "deduction_type": _first(row, "DeductionType", "DeductionTypeID", "deductionType", "deduction_type"),
        "deduction_status": _first(row, "DeductionStatus", "deductionStatus", "deduction_status"),
        "deduction_amount": _amount(_first(row, "DeductionAmount", "deductionAmount", "deduction_amount")),
        "principal_amount": _amount(_first(row, "PrincipalAmount", "principalAmount", "principal_amount")),
        "reducing_balance": _amount(_first(row, "ReducingBalance", "reducingBalance", "reducing_balance")),
        "total_installment": _first(row, "TotalInstallment", "totalInstallment", "total_installment"),
        "installment_count": _first(row, "InstallmentCount", "installmentCount", "installment_count"),
        "remaining_day": _first(row, "RemainingDay", "remainingDay", "remaining_day"),
        "effective_month": _text(_first(row, "EffectiveMonth", "effectiveMonth", "effective_month")),
        "effective_date": _text(_first(row, "EffectiveDate", "effectiveDate", "effective_date")),
        "review_date": _text(_first(row, "ReviewDate", "reviewDate", "review_date")),
        "approve_date": _text(_first(row, "ApproveDate", "approveDate", "approve_date")),
        "settlement_date": _text(_first(row, "SettlementDate", "settlementDate", "settlement_date")),
        "is_own_deduction": own,
    }


def normalize_official_cdas_snapshot(
    raw_snapshot: dict[str, Any],
    *,
    own_deduction_status: int | None = None,
) -> dict[str, Any]:
    """Convert the official CDAS response into a stable LoanHub archive shape.

    The provider payload is preserved under ``official_api`` for auditability,
    while compatibility fields let the existing Analysis History database store
    official responses without ever persisting pasted CDAS screen text.

    No booking approval is inferred here. An official refresh is a read action,
    so ``decision`` remains REVIEW_REQUIRED until a separate controlled workflow
    deliberately applies LoanHub booking rules.

    Provider timestamps and response row ordering are excluded as version noise:
    refreshing unchanged material data therefore reuses the existing history
    version instead of manufacturing duplicates.
    """

    employee = raw_snapshot.get("employee") if isinstance(raw_snapshot.get("employee"), dict) else {}
    all_rows = _stable_provider_rows(raw_snapshot.get("deductions"))
    own_rows_value = raw_snapshot.get("own_deductions")
    own_rows = _stable_provider_rows(own_rows_value)

    employee_no = _text(_first(employee, "EmployeeNo", "employeeNo", "employee_no"))
    name = _text(_first(employee, "Name", "name"))
    surname = _text(_first(employee, "Surname", "surname"))
    full_name = " ".join(value for value in (name, surname) if value) or None
    affordability = _amount(raw_snapshot.get("affordability"))

    normalized_all = [_normalize_deduction(row, own=False) for row in all_rows]
    normalized_own = [_normalize_deduction(row, own=True) for row in own_rows]

    total_monthly = sum(row["deduction_amount"] for row in normalized_all)
    active_monthly = sum(
        row["deduction_amount"]
        for row in normalized_all
        if _is_active_status(row["deduction_status"])
    )
    own_monthly = sum(row["deduction_amount"] for row in normalized_own)

    if affordability < 0:
        capacity_status = "NEGATIVE_AVAILABLE"
    elif affordability == 0:
        capacity_status = "NO_HEADROOM"
    else:
        capacity_status = "AVAILABLE"

    return {
        "source": "CDAS_API",
        "source_version": "1.5",
        "profile": {
            "employee_no": employee_no,
            "name": name,
            "surname": surname,
            "full_name": full_name,
            "date_of_birth": _text(_first(employee, "DOB", "DateOfBirth", "dateOfBirth", "date_of_birth")),
            "department": _text(_first(employee, "Department", "department")),
            "joining_date": _text(_first(employee, "JoiningDate", "joiningDate", "joining_date")),
            "end_date": _text(_first(employee, "TerminationDate", "terminationDate", "termination_date")),
            "nid": None,
            "employer": None,
            "gender": None,
            "early_retirement_date": None,
            "compulsory_retirement_date": None,
        },
        "capacity": {
            "max_available_deduction_amount": affordability,
            "max_available_after_selected_deductions": None,
            "assessed_available_amount": affordability,
            "booking_threshold_amount": 1.0,
            "booking_allowed": False,
            "status": capacity_status,
            "shortfall_amount": abs(min(affordability, 0.0)),
        },
        "booking_term": {
            "amount_owing": None,
            "monthly_available_deduction": affordability,
            "months_required": None,
            "calculation": None,
        },
        "retirement_analysis": {
            "early_retirement_date": None,
            "compulsory_retirement_date": None,
            "days_until_early_retirement": None,
            "days_until_compulsory_retirement": None,
        },
        "application_context": {
            "new_deduction_agency_code": None,
            "new_deduction_agency_name": None,
            "current_cdas_agency_code": None,
            "current_cdas_agency_name": None,
            "agency_auto_detected": False,
        },
        "decision": "REVIEW_REQUIRED",
        "decision_message": (
            "Official CDAS API snapshot archived. This refresh does not by itself "
            "approve, register, modify, settle, or book a deduction."
        ),
        "next_possible_booking_date": None,
        "reported_active_monthly_deductions": round(active_monthly, 2),
        "total_monthly_deductions": round(total_monthly, 2),
        "own_monthly_deductions": round(own_monthly, 2),
        "competitor_monthly_deductions": round(max(total_monthly - own_monthly, 0.0), 2),
        "excluded_monthly_deductions": 0.0,
        "data_quality_issue_count": 0,
        "data_quality_issues": [],
        "own_bookings": normalized_own,
        "opportunity": None,
        "deductions": normalized_all,
        "official_api": {
            "employee": employee,
            "affordability": affordability,
            "deductions": all_rows,
            "own_deductions": own_rows if isinstance(own_rows_value, list) else None,
            "own_deduction_status": own_deduction_status,
        },
    }
