"""Strict branch-directory authorization and safe projection for LoanHub.

Only the actual FastAPI tenant context may supply these values. Client-supplied
company/branch parameters cannot enlarge the caller's scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MANAGEMENT = frozenset({"company_owner", "company_admin"})


@dataclass(frozen=True)
class BranchGrant:
    company_id: str
    branch_id: str | None
    role: str
    company_wide: bool


def _str(value: Any) -> str:
    return str(getattr(value, "value", value)) if value is not None else ""


def verified_branch_grant(context: Any) -> BranchGrant:
    """Fail closed for platform users and company staff without a branch."""
    user = getattr(context, "user", None)
    staff = getattr(context, "staff", None)
    company = getattr(context, "company", None)
    company_id = _str(getattr(context, "company_id", None))
    if (not user or not getattr(user, "is_active", False) or
            not staff or not getattr(staff, "is_active", False) or
            not company or not getattr(company, "is_active", False) or
            not company_id or getattr(context, "is_platform_admin", False) or
            _str(getattr(staff, "company_id", None)) != company_id or
            _str(getattr(staff, "user_id", None)) != _str(getattr(user, "id", None))):
        raise PermissionError("Active tenant membership required")
    role = _str(getattr(staff, "role", None))
    wide = role in MANAGEMENT
    branch_id = _str(getattr(context, "branch_id", None)) or None
    if not wide and not branch_id:
        raise PermissionError("Branch-bound membership required")
    if branch_id != (_str(getattr(staff, "branch_id", None)) or None):
        raise PermissionError("Membership branch mismatch")
    return BranchGrant(company_id, branch_id, role, wide)


def safe_branch_row(row: Any, grant: BranchGrant) -> dict[str, str | None]:
    if (_str(getattr(row, "company_id", None)) != grant.company_id or
            (not grant.company_wide and _str(getattr(row, "id", None)) != grant.branch_id)):
        raise PermissionError("Branch projection scope mismatch")
    return {
        "id": _str(getattr(row, "id")),
        "company_id": grant.company_id,
        "branch_id": _str(getattr(row, "id")),
        "name": _str(getattr(row, "name")),
        "status": "active" if getattr(row, "is_active", False) else "inactive",
    }
