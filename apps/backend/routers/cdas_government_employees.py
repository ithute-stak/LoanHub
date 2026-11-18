"""Read-only, tenant-isolated discovery of existing employee-number records.

Discovery is not CDAS verification or permission to create payroll mandates.
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.models.lending_operations import CDASPayrollProfile
from database.models.origination import BorrowerEmploymentProfile
from database.session import get_db
from routers.cdas_api import _require_company_manager

router = APIRouter(prefix="/cdas/government-employees", tags=["CDAS"])

# Explicit cap: do not pretend the results cover the entire register if the cap is hit.
SOURCE_LIMIT = 5001
PAGE_SIZE_LIMIT = 100


def assemble_discovery(payroll_rows, employment_rows):
    """Flag collisions across borrowers; never merge by employee number alone."""
    grouped = defaultdict(lambda: {"borrowers": set(), "sources": set(), "verified_borrowers": set()})
    for source, rows in (("payroll", payroll_rows), ("employment", employment_rows)):
        for row in rows:
            number = str(row.employee_number or "").strip()
            if not number:
                continue
            key = number.casefold()
            item = grouped[key]
            item["borrowers"].add(str(row.borrower_id))
            item["sources"].add(source)
            if source == "payroll" and row.verified:
                item["verified_borrowers"].add(str(row.borrower_id))
            item.setdefault("employee_number", number)

    entries = []
    for _, item in sorted(grouped.items()):
        borrowers = sorted(item["borrowers"])
        ambiguous = len(borrowers) != 1
        verified = not ambiguous and borrowers[0] in item["verified_borrowers"]
        entries.append({
            "employee_number": item["employee_number"],
            "borrower_id": borrowers[0] if not ambiguous else None,
            "sources": sorted(item["sources"]),
            "status": "identity_conflict" if ambiguous else ("locally_verified" if verified else "requires_verification"),
            "requires_manual_review": ambiguous,
        })
    return entries


@router.get("")
def list_government_employee_candidates(
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=50, ge=1, le=PAGE_SIZE_LIMIT),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """List employee-number candidates belonging to the current company only.

    No provider calls, salary disclosure, mandate changes, or automatic identity linking.
    Company managers only until branch ownership can be proven for both sources.
    """
    _require_company_manager(context)
    assert context.company_id is not None
    payroll = (
        db.query(CDASPayrollProfile)
        .filter(CDASPayrollProfile.company_id == context.company_id)
        .order_by(CDASPayrollProfile.employee_number, CDASPayrollProfile.borrower_id)
        .limit(SOURCE_LIMIT)
        .all()
    )
    employment = (
        db.query(BorrowerEmploymentProfile)
        .filter(BorrowerEmploymentProfile.company_id == context.company_id)
        .order_by(BorrowerEmploymentProfile.employee_number, BorrowerEmploymentProfile.borrower_id)
        .limit(SOURCE_LIMIT)
        .all()
    )
    truncated = len(payroll) == SOURCE_LIMIT or len(employment) == SOURCE_LIMIT
    if truncated:
        # A truncated register must never be represented as "all clients".
        return {"complete": False, "items": [], "total": None,
                "message": "Register exceeds the safe source cap; use a database-paginated discovery job."}
    entries = assemble_discovery(payroll, employment)
    start = (page - 1) * page_size
    return {"complete": True, "total": len(entries), "page": page,
            "page_size": page_size, "items": entries[start:start + page_size],
            "note": "Employee-number candidates only; no live CDAS verification performed."}
