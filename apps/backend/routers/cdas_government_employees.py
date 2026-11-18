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


# Phase 2: preview an authorised, borrower-bound CDAS identity check.
# Do not mark profiles verified until a separate reviewed action is implemented.
from datetime import date
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from database.models.borrower import Borrower
from database.models.person import Person
from integrations.cdas import CdasError
from services.cdas_config_service import get_company_cdas_client
from routers.cdas_api import (
    _prepare_cdas_business_operation,
    _record_cdas_business_operation,
    _cdas_http_error,
)


class EmployeeVerificationPreviewRequest(BaseModel):
    borrower_id: UUID
    employee_number: str = Field(min_length=1, max_length=100)
    authorisation_confirmed: bool = False


def _normalise_identity(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def compare_employee_identity(*, person: Person, employee: dict, expected_number: str) -> list[str]:
    """Fail closed on missing or mismatched authoritative name/DOB fields."""
    mismatches = []
    if _normalise_identity(employee.get("EmployeeNo")) != _normalise_identity(expected_number):
        mismatches.append("employee_number_mismatch")
    if not person.first_name or _normalise_identity(employee.get("Name")) != _normalise_identity(person.first_name):
        mismatches.append("given_name_mismatch_or_missing")
    if not person.last_name or _normalise_identity(employee.get("Surname")) != _normalise_identity(person.last_name):
        mismatches.append("surname_mismatch_or_missing")
    dob = str(employee.get("DOB") or "")[:10]
    if not person.date_of_birth or dob != person.date_of_birth.isoformat():
        mismatches.append("date_of_birth_mismatch_or_missing")
    if employee.get("TerminationDate"):
        mismatches.append("employment_terminated")
    return mismatches


@router.post("/verification-preview")
async def preview_government_employee_verification(
    payload: EmployeeVerificationPreviewRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Check CDAS identity for an unambiguous company borrower without writing profile data."""
    _require_company_manager(context)
    assert context.company_id is not None
    if not payload.authorisation_confirmed:
        raise HTTPException(status_code=409, detail="Confirm the lawful authority for this employee verification")
    number = payload.employee_number.strip()
    if not number:
        raise HTTPException(status_code=422, detail="Employee number is required")

    number_expr = func.lower(func.trim(CDASPayrollProfile.employee_number))
    employment_expr = func.lower(func.trim(BorrowerEmploymentProfile.employee_number))
    payroll = db.query(CDASPayrollProfile).filter(
        CDASPayrollProfile.company_id == context.company_id,
        number_expr == number.casefold(),
    ).all()
    employment = db.query(BorrowerEmploymentProfile).filter(
        BorrowerEmploymentProfile.company_id == context.company_id,
        employment_expr == number.casefold(),
    ).all()
    linked_ids = {row.borrower_id for row in payroll + employment}
    if linked_ids != {payload.borrower_id}:
        raise HTTPException(status_code=409, detail="Missing or conflicting employee-to-borrower mapping; manual review required")

    borrower = db.query(Borrower).filter(Borrower.id == payload.borrower_id).first()
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found")
    person = db.query(Person).filter(Person.user_id == borrower.user_id).first()
    if person is None:
        raise HTTPException(status_code=409, detail="Borrower identity details are incomplete")

    # Only a non-mutating provider lookup is permitted here.
    environment = _prepare_cdas_business_operation(
        db, company_id=context.company_id, operation_type="employee_verification"
    )
    try:
        client = get_company_cdas_client(db, context.company_id)
        employee = await client.get_employee_details(number)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc

    errors = compare_employee_identity(person=person, employee=employee, expected_number=number)
    _record_cdas_business_operation(
        db, context=context, environment=environment,
        operation_type="employee_verification", source_reference=str(payload.borrower_id),
    )
    return {
        "ok": True,
        "borrower_id": str(payload.borrower_id),
        "identity_match": not errors,
        "review_required": bool(errors),
        "review_reason_codes": errors,
        "source": "CDAS employee details",
        "payroll_profile_updated": False,
        "affordability_checked": False,
        "deduction_changed": False,
    }
