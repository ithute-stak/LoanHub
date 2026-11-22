"""Minimal authorized loan/payment directory rows; NOT financial ledger balances.

All amounts, allocation details, payer/beneficiary contact, payment provider
payloads and policy inputs remain exclusively behind existing APIs.
"""
from __future__ import annotations

from typing import Any

from services.data_center_branch_projection import BranchGrant, _str


def safe_loan_row(row: Any, grant: BranchGrant) -> dict[str, str | None]:
    company_id = _str(getattr(row, "company_id", None))
    branch_id = _str(getattr(row, "branch_id", None)) or None
    if company_id != grant.company_id:
        raise PermissionError("Cross-company loan projection denied")
    if not grant.company_wide and branch_id != grant.branch_id:
        raise PermissionError("Cross-branch loan projection denied")
    loan_id = _str(getattr(row, "id", None))
    borrower_id = _str(getattr(row, "borrower_id", None))
    if not loan_id or not borrower_id:
        raise PermissionError("Invalid loan identifiers")
    return {
        "id": loan_id,
        "company_id": grant.company_id,
        "branch_id": branch_id,
        "borrower_id": borrower_id,
        "status": _str(getattr(row, "status", None)),
    }


def require_payment_directory_management(grant: BranchGrant) -> None:
    # Payments lack a direct branch_id, and some have no loan. Do not
    # infer branch authority from another table or publish to all staff.
    if not grant.company_wide or grant.role not in {"company_owner", "company_admin"}:
        raise PermissionError("Company management required for payment directory")


def safe_payment_row(row: Any, grant: BranchGrant) -> dict[str, str | None]:
    require_payment_directory_management(grant)
    if _str(getattr(row, "company_id", None)) != grant.company_id:
        raise PermissionError("Cross-company payment projection denied")
    payment_id = _str(getattr(row, "id", None))
    if not payment_id:
        raise PermissionError("Invalid payment identifier")
    return {
        "id": payment_id,
        "company_id": grant.company_id,
        "branch_id": None,
        "loan_id": _str(getattr(row, "loan_id", None)) or None,
        "status": _str(getattr(row, "status", None)),
    }
