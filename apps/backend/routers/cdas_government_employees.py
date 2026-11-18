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


# Phase 3: a fresh, read-only CDAS affordability decision for one borrower.
# A previous preview must never be trusted as proof of an unchanged identity.
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pydantic import field_validator
from database.models.origination import OriginationPolicy
from services.quick_loan_affordability_service import quick_loan_affordability


class GovernmentEmployeeAffordabilityRequest(EmployeeVerificationPreviewRequest):
    proposed_monthly_installment: Decimal = Field(gt=Decimal("0"), max_digits=15, decimal_places=2)


def assess_verified_cdas_capacity(*, borrower, policy, installment: Decimal, capacity: Decimal) -> dict:
    """Reuse LoanHub's existing lending-policy engine; no approval side effect."""
    if not capacity.is_finite() or capacity < 0:
        raise ValueError("Invalid CDAS affordability response")
    return quick_loan_affordability(
        borrower=borrower,
        policy=policy,
        proposed_installment=installment,
        live_cdas_affordability=capacity,
    )


@router.post("/affordability-preview")
async def preview_government_employee_affordability(
    payload: GovernmentEmployeeAffordabilityRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Obtain fresh CDAS identity + capacity, then apply the existing tenant policy.

    This endpoint intentionally does not persist an assessment or approve a loan.
    """
    _require_company_manager(context)
    assert context.company_id is not None
    if not payload.authorisation_confirmed:
        raise HTTPException(status_code=409, detail="Confirm lawful authority before contacting CDAS")
    number = payload.employee_number.strip()
    if not number:
        raise HTTPException(status_code=422, detail="Employee number is required")

    payroll = db.query(CDASPayrollProfile).filter(
        CDASPayrollProfile.company_id == context.company_id,
        func.lower(func.trim(CDASPayrollProfile.employee_number)) == number.casefold(),
    ).all()
    employment = db.query(BorrowerEmploymentProfile).filter(
        BorrowerEmploymentProfile.company_id == context.company_id,
        func.lower(func.trim(BorrowerEmploymentProfile.employee_number)) == number.casefold(),
    ).all()
    if {row.borrower_id for row in payroll + employment} != {payload.borrower_id}:
        raise HTTPException(status_code=409, detail="Employee number has missing or conflicting borrower links")

    borrower = db.query(Borrower).filter(Borrower.id == payload.borrower_id).first()
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found")
    person = db.query(Person).filter(Person.user_id == borrower.user_id).first()
    if person is None:
        raise HTTPException(status_code=409, detail="Borrower identity is incomplete")
    policy = db.query(OriginationPolicy).filter(
        OriginationPolicy.company_id == context.company_id,
        OriginationPolicy.is_active.is_(True),
    ).first()
    if policy is None:
        raise HTTPException(status_code=409, detail="An active company affordability policy is required")

    environment = _prepare_cdas_business_operation(
        db, company_id=context.company_id, operation_type="employee_verification"
    )
    try:
        client = get_company_cdas_client(db, context.company_id)
        employee = await client.get_employee_details(number)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    _record_cdas_business_operation(
        db, context=context, environment=environment, operation_type="employee_verification",
        source_reference=str(payload.borrower_id),
    )
    mismatches = compare_employee_identity(
        person=person, employee=employee, expected_number=number,
    )
    if mismatches:
        # Do not spend another provider request on an identity that does not match.
        return {
            "ok": False, "status": "identity_review_required",
            "borrower_id": str(payload.borrower_id),
            "review_reason_codes": mismatches,
            "affordability_checked": False,
            "loan_approved": False, "deduction_changed": False,
        }

    environment = _prepare_cdas_business_operation(
        db, company_id=context.company_id, operation_type="affordability"
    )
    try:
        capacity = await client.check_affordability(number)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    _record_cdas_business_operation(
        db, context=context, environment=environment, operation_type="affordability",
        source_reference=str(payload.borrower_id),
    )
    try:
        amount = Decimal(str(capacity))
        assessment = assess_verified_cdas_capacity(
            borrower=borrower, policy=policy,
            installment=payload.proposed_monthly_installment, capacity=amount,
        )
    except (ValueError, InvalidOperation) as exc:
        raise HTTPException(status_code=502, detail="CDAS returned an unusable affordability value") from exc
    return {
        "ok": True, "status": "assessment_preview",
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "borrower_id": str(payload.borrower_id),
        "employee_identity_verified_for_request": True,
        "cdas_environment": environment,
        "cdas_monthly_capacity": str(amount),
        "currency": "LSL",
        "assessment": assessment,
        "assessment_persisted": False,
        "pdf_generated": False,
        "loan_approved": False,
        "deduction_changed": False,
    }


# Phase 4: capture the actual server-calculated result in LoanHub's append-only
# audit ledger, then regenerate a report from that exact archived record.
# A dedicated assessment table can supersede this interim audit-backed store.
from uuid import uuid4
from fastapi.responses import Response
from database.models.audit_log import AuditLog
from services.cdas_affordability_pdf import build_government_affordability_pdf


@router.post("/affordability-records")
async def create_government_affordability_record(
    payload: GovernmentEmployeeAffordabilityRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Perform fresh checks once and persist only the verified server response."""
    _require_company_manager(context)
    result = await preview_government_employee_affordability(payload, context, db)
    if result.get("status") != "assessment_preview":
        return result  # No record for an identity mismatch.

    assessment = result["assessment"]
    reference = "CDAS-AFF-" + uuid4().hex[:16].upper()
    snapshot = {
        "reference": reference,
        "employee_number": payload.employee_number.strip(),
        "borrower_id": str(payload.borrower_id),
        "assessed_at": result["assessed_at"],
        "identity_status": "Matched against CDAS for this assessment",
        "cdas_environment": result["cdas_environment"],
        "cdas_capacity": result["cdas_monthly_capacity"],
        "proposed_installment": assessment["proposed_installment"],
        "maximum_affordable_installment": assessment["maximum_affordable_installment"],
        "decision": assessment["decision"],
        "policy_version": assessment["policy_version"],
        "assessment": assessment,
    }
    log = AuditLog(
        user_id=context.user.id,
        company_id=context.company_id,
        branch_id=context.branch_id,
        action="government_employee_affordability_assessed",
        table_name="cdas_government_affordability",
        entity_type="affordability_assessment",
        record_id=payload.borrower_id,
        description="Read-only CDAS affordability assessment captured for PDF reproduction",
        actor_role=getattr(context.role, "value", str(context.role)),
        severity="info",
        status="success",
        event_data={"snapshot": snapshot},
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {
        "ok": True,
        "status": "assessment_recorded",
        "reference": reference,
        "record_id": str(log.id),
        "borrower_id": str(payload.borrower_id),
        "assessed_at": snapshot["assessed_at"],
        "decision": snapshot["decision"],
        "pdf_path": "/api/v1/cdas/government-employees/affordability-records/" + str(log.id) + "/pdf",
        "loan_approved": False, "deduction_changed": False,
    }


@router.get("/affordability-records/{record_id}/pdf")
def download_government_affordability_report(
    record_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Render only an assessment belonging to the authenticated company."""
    _require_company_manager(context)
    assert context.company_id is not None
    log = db.query(AuditLog).filter(
        AuditLog.id == record_id,
        AuditLog.company_id == context.company_id,
        AuditLog.action == "government_employee_affordability_assessed",
        AuditLog.entity_type == "affordability_assessment",
    ).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Assessment record not found")
    snapshot = (log.event_data or {}).get("snapshot")
    if not isinstance(snapshot, dict):
        raise HTTPException(status_code=409, detail="Stored assessment snapshot is unavailable")
    if snapshot.get("borrower_id") != str(log.record_id):
        raise HTTPException(status_code=409, detail="Stored assessment identity failed validation")
    report = build_government_affordability_pdf(
        db=db, company=context.company, snapshot=snapshot,
    )
    return Response(
        content=report, media_type="application/pdf",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": 'attachment; filename="cdas-affordability-' + str(log.id) + '.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )


# Phase 5a: management history and consolidated reporting.
# These endpoints are deliberately read-only; bulk CDAS calls remain disabled.
from services.cdas_affordability_summary_pdf import build_government_affordability_summary_pdf

MAX_REPORT_RECORDS = 500


def stored_assessment_summary(record: AuditLog) -> dict:
    """Allowlist non-sensitive fields from the company-scoped archived snapshot."""
    data = (record.event_data or {}).get("snapshot")
    if not isinstance(data, dict) or data.get("borrower_id") != str(record.record_id):
        raise ValueError("Assessment record integrity check failed")
    return {
        "record_id": str(record.id),
        "reference": data.get("reference"),
        "assessed_at": data.get("assessed_at"),
        "employee_number": data.get("employee_number"),
        "borrower_id": data.get("borrower_id"),
        "cdas_capacity": data.get("cdas_capacity"),
        "maximum_affordable_installment": data.get("maximum_affordable_installment"),
        "proposed_installment": data.get("proposed_installment"),
        "decision": data.get("decision"),
        "policy_version": data.get("policy_version"),
        "pdf_path": "/api/v1/cdas/government-employees/affordability-records/"
                    + str(record.id) + "/pdf",
    }


def _company_assessment_query(db: Session, company_id: UUID):
    return db.query(AuditLog).filter(
        AuditLog.company_id == company_id,
        AuditLog.action == "government_employee_affordability_assessed",
        AuditLog.entity_type == "affordability_assessment",
        AuditLog.status == "success",
    )


@router.get("/affordability-records")
def list_government_affordability_records(
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=50, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Display saved company assessments, not a fresh CDAS balance."""
    _require_company_manager(context)
    assert context.company_id is not None
    query = _company_assessment_query(db, context.company_id)
    count = query.count()
    records = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    entries = []
    for record in records:
        try:
            entries.append(stored_assessment_summary(record))
        except ValueError:
            # Do not allow a malformed saved record to masquerade as valid.
            entries.append({"record_id": str(record.id), "status": "integrity_review_required"})
    return {
        "total": count, "page": page, "page_size": page_size, "items": entries,
        "note": "Historical assessments only; CDAS capacity is not refreshed.",
    }


@router.get("/affordability-summary.pdf")
def download_government_affordability_summary(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Full-company summary (maximum 500 records); never silently truncate."""
    _require_company_manager(context)
    assert context.company_id is not None
    query = _company_assessment_query(db, context.company_id)
    records = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(
        MAX_REPORT_RECORDS + 1
    ).all()
    if len(records) > MAX_REPORT_RECORDS:
        raise HTTPException(
            status_code=409,
            detail="Too many assessments for one PDF; use paginated history until batch export is available",
        )
    try:
        items = [stored_assessment_summary(record) for record in records]
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail="A saved assessment failed integrity validation"
        ) from exc
    pdf = build_government_affordability_summary_pdf(
        db=db, company=context.company, rows=items,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'attachment; filename="cdas-affordability-summary.pdf"',
        },
    )


# Phase 5B preflight: bounded selection with budget and identity checks only.
# This endpoint deliberately does not queue, run, or charge CDAS operations.
from services.cdas_request_budget import get_cdas_request_budget_status
from routers.cdas_api import _company_cdas_environment


class BulkAffordabilitySelection(BaseModel):
    borrower_id: UUID
    employee_number: str = Field(min_length=1, max_length=100)
    proposed_monthly_installment: Decimal = Field(gt=Decimal("0"), max_digits=15, decimal_places=2)


class BulkAffordabilityPreflightRequest(BaseModel):
    employees: list[BulkAffordabilitySelection] = Field(min_length=1, max_length=20)


def validate_bulk_selection(employees: list[BulkAffordabilitySelection]) -> list[str]:
    """Require unique borrower IDs and employee numbers; never guess duplicates."""
    errors = []
    seen_borrowers = set()
    seen_numbers = set()
    for item in employees:
        number = item.employee_number.strip().casefold()
        if not number:
            errors.append("blank_employee_number")
        if item.borrower_id in seen_borrowers:
            errors.append("duplicate_borrower_selection")
        if number in seen_numbers:
            errors.append("duplicate_employee_number_selection")
        seen_borrowers.add(item.borrower_id)
        seen_numbers.add(number)
    return sorted(set(errors))


def _bulk_candidate_status(
    db: Session, *, company_id: UUID, selection: BulkAffordabilitySelection
) -> str:
    """Read both company-controlled sources and flag borrower collisions."""
    number = selection.employee_number.strip().casefold()
    payroll = db.query(CDASPayrollProfile).filter(
        CDASPayrollProfile.company_id == company_id,
        func.lower(func.trim(CDASPayrollProfile.employee_number)) == number,
    ).all()
    employment = db.query(BorrowerEmploymentProfile).filter(
        BorrowerEmploymentProfile.company_id == company_id,
        func.lower(func.trim(BorrowerEmploymentProfile.employee_number)) == number,
    ).all()
    ids = {row.borrower_id for row in payroll + employment}
    if not ids:
        return "employee_not_registered"
    if ids != {selection.borrower_id}:
        return "identity_conflict"
    borrower = db.query(Borrower).filter(Borrower.id == selection.borrower_id).first()
    if borrower is None:
        return "borrower_not_found"
    person = db.query(Person).filter(Person.user_id == borrower.user_id).first()
    if person is None or not person.first_name or not person.last_name or not person.date_of_birth:
        return "identity_incomplete"
    return "ready_for_live_verification"


@router.post("/bulk/preflight")
def preflight_bulk_government_affordability(
    payload: BulkAffordabilityPreflightRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Safely preview a bounded group of candidates, never call CDAS."""
    _require_company_manager(context)
    assert context.company_id is not None
    errors = validate_bulk_selection(payload.employees)
    if errors:
        raise HTTPException(status_code=422, detail={"selection_errors": errors})
    policy = db.query(OriginationPolicy).filter(
        OriginationPolicy.company_id == context.company_id,
        OriginationPolicy.is_active.is_(True),
    ).first()
    if policy is None:
        raise HTTPException(status_code=409, detail="Active company affordability policy required")
    environment = _company_cdas_environment(db, context.company_id)
    budget = get_cdas_request_budget_status(
        db, company_id=context.company_id, environment=environment,
    )
    candidates = []
    for selection in payload.employees:
        status = _bulk_candidate_status(
            db, company_id=context.company_id, selection=selection,
        )
        candidates.append({
            "borrower_id": str(selection.borrower_id),
            "employee_number": selection.employee_number.strip(),
            "status": status,
            "proposed_monthly_installment": str(selection.proposed_monthly_installment),
        })
    ready_count = sum(row["status"] == "ready_for_live_verification" for row in candidates)
    # Lower-bound estimate: employee detail + capacity check. Authentication,
    # retries and overhead may consume additional daily request credits.
    estimated_min_requests = 2 * ready_count
    remaining = int(budget["remaining"])
    return {
        "ok": True,
        "mode": "preflight_only",
        "execution_enabled": False,
        "batch_created": False,
        "provider_contacted": False,
        "candidate_count": len(candidates),
        "ready_count": ready_count,
        "review_count": len(candidates) - ready_count,
        "minimum_estimated_provider_requests": estimated_min_requests,
        "budget_remaining_at_preflight": remaining,
        "budget_preflight_sufficient": estimated_min_requests < remaining,
        "request_budget_warning": (
            "Estimate excludes authentication, retries and other concurrent CDAS activity; "
            "the provider budget must be rechecked when execution starts."
        ),
        "candidates": candidates,
    }
