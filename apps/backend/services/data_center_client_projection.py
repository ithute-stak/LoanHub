"""Strict tenant and branch authorized borrower-account directory projection.

No personally identifiable data, bank details, salary, or opening-fee amounts.
These pages are NOT the complete multi-resource Data Center snapshot.
"""
from __future__ import annotations

from typing import Any

from services.data_center_branch_projection import BranchGrant, _str


def safe_client_row(row: Any, grant: BranchGrant) -> dict[str, str | None]:
    company_id = _str(getattr(row, "company_id", None))
    branch_id = _str(getattr(row, "branch_id", None)) or None
    if company_id != grant.company_id:
        raise PermissionError("Cross-company borrower account denied")
    if not grant.company_wide and branch_id != grant.branch_id:
        raise PermissionError("Cross-branch borrower account denied")
    account_id = _str(getattr(row, "id", None))
    borrower_id = _str(getattr(row, "borrower_id", None))
    if not account_id or not borrower_id:
        raise PermissionError("Invalid borrower account identity")
    return {
        "id": account_id,
        "company_id": grant.company_id,
        "branch_id": branch_id,
        "borrower_id": borrower_id,
        "status": _str(getattr(row, "status", None)),
    }
