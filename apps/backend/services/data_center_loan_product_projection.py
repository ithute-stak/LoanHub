"""Company-scoped, allowlisted loan-product directory projection.

Loan products are company-wide: the branch_id returned here represents the
viewer's verified cache scope, not an ownership column on loan_products.
No interest rate, fees, terms, pricing, or internal policy is exposed.
"""
from __future__ import annotations

from typing import Any

from services.data_center_branch_projection import BranchGrant


def safe_loan_product_row(row: Any, grant: BranchGrant) -> dict[str, str | None]:
    if str(getattr(row, "company_id", "")) != grant.company_id:
        raise PermissionError("Cross-company loan product projection denied")
    product_id = str(getattr(row, "id", ""))
    if not product_id or product_id == "None":
        raise PermissionError("Invalid product identifier")
    name = getattr(row, "name", None)
    if not isinstance(name, str):
        raise PermissionError("Invalid product display name")
    return {
        "id": product_id,
        "company_id": grant.company_id,
        # Products are company-wide, but the projection cache is branch-scoped.
        "branch_id": None if grant.company_wide else grant.branch_id,
        "name": name,
        "status": "active" if getattr(row, "is_active", False) else "inactive",
    }
