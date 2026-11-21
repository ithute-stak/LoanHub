"""Read-only minimal staff directory, restricted to tenant management.

Do not project names, email, phone, salary, identity, or credentials.
"""
from __future__ import annotations

from typing import Any

from services.data_center_branch_projection import BranchGrant, _str


def require_staff_directory_management(grant: BranchGrant) -> None:
    if not grant.company_wide or grant.role not in {"company_owner", "company_admin"}:
        raise PermissionError("Staff directory requires active company management")


def safe_staff_row(row: Any, grant: BranchGrant) -> dict[str, str | None]:
    require_staff_directory_management(grant)
    if _str(getattr(row, "company_id", None)) != grant.company_id:
        raise PermissionError("Cross-company staff projection denied")
    row_id = _str(getattr(row, "id", None))
    if not row_id:
        raise PermissionError("Invalid staff identifier")
    role = _str(getattr(row, "role", None))
    if not role:
        raise PermissionError("Invalid staff role")
    return {
        "id": row_id,
        "company_id": grant.company_id,
        "branch_id": _str(getattr(row, "branch_id", None)) or None,
        "role": role,
        "status": "active" if getattr(row, "is_active", False) else "inactive",
    }
