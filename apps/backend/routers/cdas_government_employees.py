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
    consent_evidence_reference: str | None = Field(default=None, max_length=200)


class RecordedGovernmentEmployeeAffordabilityRequest(GovernmentEmployeeAffordabilityRequest):
    """Every billable stored assessment requires a durable replay key."""
    idempotency_key: str = Field(min_length=12, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    consent_evidence_reference: str = Field(min_length=6, max_length=200)


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
    _require_approved_affordability_consent(
        db, company_id=context.company_id, borrower_id=payload.borrower_id,
        employee_number=number, reference=payload.consent_evidence_reference,
        operator_user_id=context.user.id,
    )

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


from database.models.documents import BorrowerDocument
from database.models.file_management import ManagedFile
from services.cdas_affordability_managed_consent_integrity import verify_managed_cdas_consent_bytes
from database.models.cdas_affordability_consent_evidence import CdasAffordabilityConsentEvidence
from services.cdas_affordability_consent_policy import PURPOSE, consent_evidence_blockers


class PendingCdasConsentEvidenceRequest(BaseModel):
    borrower_id: UUID
    document_id: UUID
    managed_file_id: UUID
    employee_number: str = Field(min_length=1, max_length=100)
    reference: str = Field(min_length=6, max_length=200)
    borrower_authorization_confirmed: bool = False


def _require_approved_affordability_consent(
    db: Session, *, company_id: UUID, borrower_id: UUID,
    employee_number: str, reference: str | None, operator_user_id: UUID,
):
    """Fail closed before contacting CDAS, including read-only live previews.

    A typed reference or a generic verified borrower file is not sufficient.
    Existing approvals must be independently checked for their exact scope.
    """
    ref = (reference or "").strip()
    if len(ref) < 6:
        raise HTTPException(status_code=409, detail="Reviewed CDAS consent evidence is required before a live lookup")
    evidence = db.query(CdasAffordabilityConsentEvidence).filter(
        CdasAffordabilityConsentEvidence.company_id == company_id,
        CdasAffordabilityConsentEvidence.borrower_id == borrower_id,
        CdasAffordabilityConsentEvidence.reference == ref,
    ).first()
    reasons = consent_evidence_blockers(
        evidence=evidence, company_id=company_id, borrower_id=borrower_id,
        employee_number=employee_number, reference=ref,
        operator_user_id=operator_user_id,
    )
    if reasons:
        raise HTTPException(
            status_code=409,
            detail={"message": "Independent CDAS consent review is required",
                    "reason_codes": reasons},
        )
    # A verified approval must still point to the same borrower document.
    # The evidence-content digest is reviewed separately; never compute it
    # from an untrusted document URL inside a CDAS request.
    document = db.query(BorrowerDocument).filter(
        BorrowerDocument.id == evidence.document_id,
        BorrowerDocument.borrower_id == borrower_id,
    ).first()
    if document is None:
        raise HTTPException(
            status_code=409,
            detail="Approved CDAS evidence document is no longer linked to this borrower",
        )
    if not getattr(evidence, "managed_file_id", None):
        raise HTTPException(
            status_code=409, detail="Approved CDAS consent lacks verified managed-file binding",
        )
    file = db.query(ManagedFile).filter(
        ManagedFile.id == evidence.managed_file_id,
        ManagedFile.company_id == company_id,
    ).first()
    verify_managed_cdas_consent_bytes(
        file=file, company_id=company_id, borrower_id=borrower_id,
        expected_digest=evidence.document_sha256,
    )
    return evidence


@router.post("/consent-evidence", status_code=201)
def submit_pending_cdas_consent_evidence(
    payload: PendingCdasConsentEvidenceRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Save a borrower-linked consent DOCUMENT for separate human review.

    No CDAS provider call, document verification, or consent approval occurs.
    The later live gate must verify the document digest and reviewer decision.
    """
    _require_company_manager(context)
    assert context.company_id is not None
    number = payload.employee_number.strip()
    reference = payload.reference.strip()
    if not payload.borrower_authorization_confirmed:
        raise HTTPException(status_code=409, detail="Borrower consent confirmation is required")
    if len(reference) < 6 or not number:
        raise HTTPException(status_code=422, detail="Valid employee number and evidence reference are required")
    payroll = db.query(CDASPayrollProfile).filter(
        CDASPayrollProfile.company_id == context.company_id,
        func.lower(func.trim(CDASPayrollProfile.employee_number)) == number.casefold(),
    ).all()
    employment = db.query(BorrowerEmploymentProfile).filter(
        BorrowerEmploymentProfile.company_id == context.company_id,
        func.lower(func.trim(BorrowerEmploymentProfile.employee_number)) == number.casefold(),
    ).all()
    if {row.borrower_id for row in payroll + employment} != {payload.borrower_id}:
        raise HTTPException(status_code=409, detail="Employee number is missing or linked to conflicting borrowers")
    document = db.query(BorrowerDocument).filter(
        BorrowerDocument.id == payload.document_id,
        BorrowerDocument.borrower_id == payload.borrower_id,
    ).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Borrower-linked evidence document not found")
    managed_file = db.query(ManagedFile).filter(
        ManagedFile.id == payload.managed_file_id,
        ManagedFile.company_id == context.company_id,
    ).first()
    # Submission is still pending; this is only a source-byte integrity check.
    # Never derive evidence from BorrowerDocument.file_url or a user-supplied hash.
    verify_managed_cdas_consent_bytes(
        file=managed_file, company_id=context.company_id,
        borrower_id=payload.borrower_id,
    )
    existing = db.query(CdasAffordabilityConsentEvidence).filter(
        CdasAffordabilityConsentEvidence.company_id == context.company_id,
        CdasAffordabilityConsentEvidence.reference == reference,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Consent evidence reference already exists")
    record = CdasAffordabilityConsentEvidence(
        company_id=context.company_id,
        borrower_id=payload.borrower_id,
        document_id=document.id,
        managed_file_id=managed_file.id,
        employee_number=number,
        reference=reference,
        purpose=PURPOSE,
        status="pending",
        borrower_authorization_confirmed=True,
        submitted_by_user_id=context.user.id,
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate consent evidence reference") from exc
    return {
        "evidence_id": str(record.id),
        "reference": record.reference,
        "status": "pending",
        "verified": False,
        "cdas_request_authorized": False,
        "note": "Awaiting independent document and consent review; no CDAS request sent",
    }


@router.get("/consent-evidence/{evidence_id}/review-document")
def download_cdas_consent_review_document(
    evidence_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Download the *specific* consent source under independent-review scope.

    This endpoint does not use the general-purpose file owner/share policy:
    the reviewer must be a company manager, not the submitter, and the
    managed file must pass the tenant, borrower, and byte-integrity checks.
    It is not a public storage URL or an approval operation.
    """
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    _require_company_manager(context)
    assert context.company_id is not None
    record = db.query(CdasAffordabilityConsentEvidence).filter(
        CdasAffordabilityConsentEvidence.id == evidence_id,
        CdasAffordabilityConsentEvidence.company_id == context.company_id,
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Consent evidence not found")
    if record.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending evidence may be reviewed")
    if record.submitted_by_user_id is None or context.user.id == record.submitted_by_user_id:
        raise HTTPException(status_code=403, detail="Submitting user cannot perform independent review")
    if not record.managed_file_id:
        raise HTTPException(status_code=409, detail="No managed consent source document")
    file = db.query(ManagedFile).filter(
        ManagedFile.id == record.managed_file_id,
        ManagedFile.company_id == context.company_id,
    ).first()
    verified_digest = verify_managed_cdas_consent_bytes(
        file=file, company_id=context.company_id, borrower_id=record.borrower_id,
    )
    # Read again for the actual response and bind it to the same verified
    # digest: never serve a different version after the integrity check.
    from services.file_service import read_file_bytes
    import hashlib
    import hmac
    content = read_file_bytes(file)
    if not hmac.compare_digest(hashlib.sha256(content).hexdigest(), verified_digest):
        raise HTTPException(status_code=409, detail="Consent source changed during review download")
    return StreamingResponse(
        BytesIO(content),
        media_type=file.mime_type,
        headers={
            "Content-Disposition": 'attachment; filename="cdas-consent-evidence"',
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(len(content)),
        },
    )


class CdasConsentApprovalRequest(BaseModel):
    """A human reviewer attests to the *exact* borrower, purpose and bytes."""
    reviewed_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_reviewed: bool
    borrower_identity_checked: bool
    borrower_consent_checked: bool
    purpose_confirmed: bool
    reason: str = Field(min_length=12, max_length=400)
    expires_at: datetime


@router.post("/consent-evidence/{evidence_id}/approve")
def approve_cdas_consent_evidence(
    evidence_id: UUID,
    payload: CdasConsentApprovalRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Require independent explicit approval with verified stored source bytes.

    No CDAS contact occurs here; approved evidence is still verified again
    immediately before each permitted individual provider operation.
    """
    from datetime import timedelta

    _require_company_manager(context)
    assert context.company_id is not None
    if not all((
        payload.document_reviewed, payload.borrower_identity_checked,
        payload.borrower_consent_checked, payload.purpose_confirmed,
    )):
        raise HTTPException(status_code=409, detail="All independent consent review checks must be confirmed")
    now = datetime.now(timezone.utc)
    expiry = payload.expires_at
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise HTTPException(status_code=422, detail="Consent expiry must include a timezone")
    expiry = expiry.astimezone(timezone.utc)
    if not now < expiry <= now + timedelta(days=90):
        raise HTTPException(status_code=409, detail="Consent must expire within 90 days")
    record = db.query(CdasAffordabilityConsentEvidence).filter(
        CdasAffordabilityConsentEvidence.id == evidence_id,
        CdasAffordabilityConsentEvidence.company_id == context.company_id,
    ).with_for_update().first()
    if record is None:
        raise HTTPException(status_code=404, detail="Consent evidence not found")
    if record.status != "pending":
        raise HTTPException(status_code=409, detail="Consent evidence is no longer awaiting review")
    if record.submitted_by_user_id is None or context.user.id == record.submitted_by_user_id:
        raise HTTPException(status_code=403, detail="An independent reviewer is required")
    if not record.borrower_authorization_confirmed or record.purpose != PURPOSE:
        raise HTTPException(status_code=409, detail="Purpose-bound borrower consent is not confirmed")
    document = db.query(BorrowerDocument).filter(
        BorrowerDocument.id == record.document_id,
        BorrowerDocument.borrower_id == record.borrower_id,
    ).first()
    if document is None or not record.managed_file_id:
        raise HTTPException(status_code=409, detail="Consent source document is missing")
    file = db.query(ManagedFile).filter(
        ManagedFile.id == record.managed_file_id,
        ManagedFile.company_id == context.company_id,
    ).first()
    digest = verify_managed_cdas_consent_bytes(
        file=file, company_id=context.company_id, borrower_id=record.borrower_id,
        expected_digest=payload.reviewed_document_sha256,
    )
    record.status = "approved"
    record.document_sha256 = digest
    record.verified_by_user_id = context.user.id
    record.verified_at = now
    record.expires_at = expiry
    db.add(AuditLog(
        user_id=context.user.id,
        company_id=context.company_id,
        branch_id=getattr(context, "branch_id", None),
        action="cdas_affordability_consent_approved",
        table_name="cdas_affordability_consent_evidence",
        entity_type="consent_evidence",
        record_id=record.id,
        description="Independent approval of purpose-specific CDAS consent evidence",
        actor_role=getattr(getattr(context, "role", None), "value", "company_manager"),
        severity="info",
        status="success",
        event_data={
            "reason": payload.reason.strip(),
            "borrower_id": str(record.borrower_id),
            "employee_number": record.employee_number,
            "document_id": str(record.document_id),
            "managed_file_id": str(record.managed_file_id),
            "document_sha256": digest,
            "consent_reference": record.reference,
            "purpose": PURPOSE,
            "expires_at": expiry.isoformat(),
            "reviewed_document": True,
            "identity_checked": True,
            "borrower_consent_checked": True,
        },
    ))
    db.commit()
    return {
        "evidence_id": str(record.id), "status": "approved",
        "document_sha256": digest, "expires_at": expiry.isoformat(),
        "cdas_request_sent": False,
        "note": "Approved consent evidence still requires fresh live-file and policy checks",
    }


class CdasConsentReviewDecision(BaseModel):
    decision: str = Field(pattern=r"^(reject|revoke)$")
    reason: str = Field(min_length=8, max_length=400)


@router.get("/consent-evidence")
def list_cdas_consent_review_queue(
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=25, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read-only tenant-scoped registry; never contacts CDAS."""
    _require_company_manager(context)
    assert context.company_id is not None
    records = db.query(CdasAffordabilityConsentEvidence).filter(
        CdasAffordabilityConsentEvidence.company_id == context.company_id,
    )
    total = records.count()
    items = records.order_by(
        CdasAffordabilityConsentEvidence.created_at.desc(),
        CdasAffordabilityConsentEvidence.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {
                "evidence_id": str(item.id),
                "borrower_id": str(item.borrower_id),
                "employee_number": item.employee_number,
                "reference": item.reference,
                "status": item.status,
                "document_id": str(item.document_id),
                "managed_file_id": str(item.managed_file_id) if item.managed_file_id else None,
                "verified": item.status == "approved",
                "cdas_request_authorized": False,
            }
            for item in items
        ],
        "note": "Review registry only. No CDAS request or automatic approval.",
    }


@router.post("/consent-evidence/{evidence_id}/decision")
def reject_or_revoke_cdas_consent_evidence(
    evidence_id: UUID,
    payload: CdasConsentReviewDecision,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Independent reviewer may reject pending evidence or revoke approval.

    Approval is intentionally unavailable until actual document integrity
    verification can be bound to an audited reviewer decision.
    """
    _require_company_manager(context)
    assert context.company_id is not None
    record = db.query(CdasAffordabilityConsentEvidence).filter(
        CdasAffordabilityConsentEvidence.id == evidence_id,
        CdasAffordabilityConsentEvidence.company_id == context.company_id,
    ).with_for_update().first()
    if record is None:
        raise HTTPException(status_code=404, detail="Consent evidence not found")
    if context.user.id == record.submitted_by_user_id:
        raise HTTPException(status_code=403, detail="Submitting user cannot review their own consent evidence")
    expected = "pending" if payload.decision == "reject" else "approved"
    if record.status != expected:
        raise HTTPException(status_code=409, detail="Consent review status is no longer eligible for this decision")
    record.status = "rejected" if payload.decision == "reject" else "revoked"
    db.add(AuditLog(
        user_id=context.user.id,
        company_id=context.company_id,
        branch_id=getattr(context, "branch_id", None),
        action="cdas_affordability_consent_" + record.status,
        table_name="cdas_affordability_consent_evidence",
        entity_type="consent_evidence",
        record_id=record.id,
        description="Independent CDAS consent review decision",
        actor_role=getattr(getattr(context, "role", None), "value", "company_manager"),
        severity="info",
        status="success",
        event_data={
            "decision": payload.decision, "reason": payload.reason.strip(),
            "borrower_id": str(record.borrower_id),
            "document_id": str(record.document_id),
            "consent_reference": record.reference,
        },
    ))
    db.commit()
    return {
        "evidence_id": str(record.id),
        "status": record.status,
        "cdas_request_authorized": False,
        "note": "Evidence closed without contacting CDAS",
    }


from services.cdas_affordability_attempts import (
    reserve_affordability_attempt,
    find_attempt,
    safe_attempt_status,
)


from database.models.cdas_affordability_attempt import CdasAffordabilityAttempt


@router.get("/affordability-attempts")
def list_government_affordability_attempts(
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=25, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read-only company attempt register for recovery after a browser restart.

    Never expose the idempotency key or other companies' attempts.
    An unresolved reservation is not proof of a provider failure.
    """
    _require_company_manager(context)
    assert context.company_id is not None
    query = db.query(CdasAffordabilityAttempt).filter(
        CdasAffordabilityAttempt.company_id == context.company_id,
    )
    total = query.count()
    attempts = query.order_by(
        CdasAffordabilityAttempt.created_at.desc(),
        CdasAffordabilityAttempt.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {
                "attempt_id": str(attempt.id),
                "borrower_id": str(attempt.borrower_id),
                "status": attempt.state,
                "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
                "record_id": str(attempt.assessment_record_id) if attempt.assessment_record_id else None,
                "requires_manual_review": attempt.state in ("reserved", "unknown", "identity_review"),
                "may_retry_provider_request": False,
            }
            for attempt in attempts
        ],
        "note": "Stored request status only. Listing attempts does not contact CDAS.",
    }


@router.get("/affordability-attempts/{idempotency_key}")
def get_government_affordability_attempt(
    idempotency_key: str,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Company-scoped status lookup; no CDAS provider operation."""
    _require_company_manager(context)
    assert context.company_id is not None
    if not 12 <= len(idempotency_key) <= 120 or not all(
        ch.isalnum() or ch in "_-" for ch in idempotency_key
    ):
        raise HTTPException(status_code=422, detail="Invalid idempotency key")
    attempt = find_attempt(
        db, company_id=context.company_id, idempotency_key=idempotency_key,
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Assessment attempt not found")
    return safe_attempt_status(attempt)


@router.post("/affordability-records")
async def create_government_affordability_record(
    payload: RecordedGovernmentEmployeeAffordabilityRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Perform fresh checks once and persist only the verified server response."""
    _require_company_manager(context)
    assert context.company_id is not None
    # Fail fast on missing authority before writing an attempt reservation.
    if not payload.authorisation_confirmed:
        raise HTTPException(status_code=409, detail="Confirm lawful authority before contacting CDAS")
    if not payload.employee_number.strip():
        raise HTTPException(status_code=422, detail="Employee number is required")
    if len(payload.consent_evidence_reference.strip()) < 6:
        raise HTTPException(status_code=422, detail="A nonblank consent evidence reference is required")
    _require_approved_affordability_consent(
        db, company_id=context.company_id, borrower_id=payload.borrower_id,
        employee_number=payload.employee_number.strip(),
        reference=payload.consent_evidence_reference,
        operator_user_id=context.user.id,
    )
    # The request schema requires a durable idempotency key before provider contact.
    attempt, created = reserve_affordability_attempt(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        borrower_id=payload.borrower_id,
        employee_number=payload.employee_number,
        installment=payload.proposed_monthly_installment,
        consent_evidence_reference=payload.consent_evidence_reference,
        idempotency_key=payload.idempotency_key,
    )
    if not created:
        if attempt.state == "completed" and attempt.assessment_record_id:
            saved = _company_assessment_query(db, context.company_id).filter(
                AuditLog.id == attempt.assessment_record_id,
                AuditLog.record_id == payload.borrower_id,
            ).first()
            if saved is not None:
                try:
                    record = stored_assessment_summary(saved)
                except ValueError:
                    record = None
                if record:
                    return {
                        "ok": True, "status": "assessment_recorded",
                        "reference": record["reference"],
                        "record_id": record["record_id"],
                        "borrower_id": record["borrower_id"],
                        "assessed_at": record["assessed_at"],
                        "decision": record["decision"],
                        "pdf_path": record["pdf_path"],
                        "idempotent_replay": True,
                        "loan_approved": False, "deduction_changed": False,
                    }
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Prior CDAS attempt exists; investigate its status before any new provider request",
                **safe_attempt_status(attempt),
            },
        )

    try:
        result = await preview_government_employee_affordability(payload, context, db)
    except Exception:
        # Even if CDAS has already been contacted, an interrupted request cannot
        # be assumed safe to retry. A crashed process leaves 'reserved' instead.
        if attempt is not None:
            db.rollback()
            attempt.state = "unknown"
            db.commit()
        raise
    if result.get("status") != "assessment_preview":
        if attempt is not None:
            attempt.state = "identity_review"
            db.commit()
        return result  # No record for an identity mismatch.

    assessment = result["assessment"]
    reference = "CDAS-AFF-" + uuid4().hex[:16].upper()
    snapshot = {
        "reference": reference,
        "employee_number": payload.employee_number.strip(),
        "borrower_id": str(payload.borrower_id),
        "assessed_at": result["assessed_at"],
        "identity_status": "Matched against CDAS for this assessment",
        "consent_evidence_reference": payload.consent_evidence_reference.strip(),
        "consent_evidence_verified": False,
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
    if attempt is not None:
        db.flush()
        attempt.state = "completed"
        attempt.assessment_record_id = log.id
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
    # Never present an incomplete archived result as a successfully completed
    # assessment. This validator is shared by history and idempotent replay.
    if any(not isinstance(data.get(field), str) or not data[field].strip()
           for field in ("reference", "assessed_at", "decision")):
        raise ValueError("Assessment archive lacks required result metadata")
    try:
        assessed_at = datetime.fromisoformat(data["assessed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Assessment archive has invalid timestamp") from exc
    if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
        raise ValueError("Assessment archive has invalid timestamp")
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


@router.get("/affordability-records/{record_id}")
def get_government_affordability_saved_record(
    record_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read exactly one company-owned saved assessment; never request CDAS."""
    _require_company_manager(context)
    assert context.company_id is not None
    record = _company_assessment_query(db, context.company_id).filter(
        AuditLog.id == record_id,
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Saved assessment not found")
    try:
        return stored_assessment_summary(record)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Saved assessment requires integrity review") from exc


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


# Phase 5D: durable draft batches only; execution is still hard-disabled.
from sqlalchemy.exc import IntegrityError
from database.models.cdas_affordability_batch import CdasAffordabilityBatch, CdasAffordabilityBatchItem
from services.cdas_affordability_bulk_jobs import batch_fingerprint, safe_batch_summary, transition_batch


class CreateBulkAffordabilityDraft(BulkAffordabilityPreflightRequest):
    idempotency_key: str = Field(min_length=12, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    consent_evidence_reference: str = Field(min_length=6, max_length=160)


@router.post("/bulk/batches", status_code=201)
def create_government_affordability_draft_batch(
    payload: CreateBulkAffordabilityDraft,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Store a resumable draft. No worker, CDAS calls, deductions or scheduled execution."""
    _require_company_manager(context)
    assert context.company_id is not None
    errors = validate_bulk_selection(payload.employees)
    if errors:
        raise HTTPException(status_code=422, detail={"selection_errors": errors})
    fingerprint = batch_fingerprint(payload.employees)
    existing = db.query(CdasAffordabilityBatch).filter(
        CdasAffordabilityBatch.company_id == context.company_id,
        CdasAffordabilityBatch.idempotency_key == payload.idempotency_key,
    ).first()
    if existing is not None:
        if (existing.request_fingerprint != fingerprint or
                existing.consent_evidence_reference != payload.consent_evidence_reference):
            raise HTTPException(status_code=409, detail="Idempotency key already used for a different batch")
        return {"batch_id": str(existing.id), "status": existing.status,
                "execution_enabled": False, "idempotent_replay": True}

    policy = db.query(OriginationPolicy).filter(
        OriginationPolicy.company_id == context.company_id,
        OriginationPolicy.is_active.is_(True),
    ).first()
    if policy is None:
        raise HTTPException(status_code=409, detail="Active company affordability policy required")

    statuses = [
        _bulk_candidate_status(db, company_id=context.company_id, selection=item)
        for item in payload.employees
    ]
    if any(status != "ready_for_live_verification" for status in statuses):
        raise HTTPException(
            status_code=409,
            detail={"message": "Resolve identity conflicts and missing records before drafting a batch",
                    "candidate_statuses": statuses},
        )
    # Confirming that a reference exists does not prove valid consent.
    # Staff must separately verify the underlying evidence before any future execution.
    batch = CdasAffordabilityBatch(
        company_id=context.company_id,
        created_by_user_id=context.user.id,
        idempotency_key=payload.idempotency_key,
        request_fingerprint=fingerprint,
        consent_evidence_reference=payload.consent_evidence_reference,
        status="draft",
        total_count=len(payload.employees),
        finished_count=0,
        execution_enabled=False,
    )
    db.add(batch)
    db.flush()
    for item in payload.employees:
        db.add(CdasAffordabilityBatchItem(
            batch_id=batch.id,
            company_id=context.company_id,
            borrower_id=item.borrower_id,
            employee_number=item.employee_number.strip().upper(),
            proposed_monthly_installment=item.proposed_monthly_installment,
            status="pending",
            attempt_count=0,
        ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(CdasAffordabilityBatch).filter(
            CdasAffordabilityBatch.company_id == context.company_id,
            CdasAffordabilityBatch.idempotency_key == payload.idempotency_key,
        ).first()
        if (existing is not None and existing.request_fingerprint == fingerprint and
                existing.consent_evidence_reference == payload.consent_evidence_reference):
            return {"batch_id": str(existing.id), "status": existing.status,
                    "execution_enabled": False, "idempotent_replay": True}
        raise HTTPException(status_code=409, detail="Batch creation conflict") from exc
    return {"batch_id": str(batch.id), "status": "draft",
            "execution_enabled": False, "idempotent_replay": False,
            "note": "Consent evidence reference supplied but not validated; no CDAS execution enabled."}


def _load_company_batch(db: Session, company_id: UUID, batch_id: UUID):
    batch = db.query(CdasAffordabilityBatch).filter(
        CdasAffordabilityBatch.id == batch_id,
        CdasAffordabilityBatch.company_id == company_id,
    ).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="Bulk batch not found")
    return batch


@router.get("/bulk/batches")
def list_government_affordability_batches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    query = db.query(CdasAffordabilityBatch).filter(
        CdasAffordabilityBatch.company_id == context.company_id,
    )
    total = query.count()
    rows = query.order_by(
        CdasAffordabilityBatch.created_at.desc(), CdasAffordabilityBatch.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [{"batch_id": str(b.id), "status": b.status,
                   "execution_enabled": False, "total_count": b.total_count,
                   "finished_count": b.finished_count} for b in rows],
    }


@router.get("/bulk/batches/{batch_id}")
def get_government_affordability_batch(
    batch_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    batch = _load_company_batch(db, context.company_id, batch_id)
    items = db.query(CdasAffordabilityBatchItem).filter(
        CdasAffordabilityBatchItem.company_id == context.company_id,
        CdasAffordabilityBatchItem.batch_id == batch.id,
    ).order_by(CdasAffordabilityBatchItem.id).all()
    return safe_batch_summary(batch, items)


@router.post("/bulk/batches/{batch_id}/cancel")
def cancel_government_affordability_batch(
    batch_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    # Compare-and-swap prevents two requests from silently changing the same job.
    updated = db.query(CdasAffordabilityBatch).filter(
        CdasAffordabilityBatch.id == batch_id,
        CdasAffordabilityBatch.company_id == context.company_id,
        CdasAffordabilityBatch.status == "draft",
        CdasAffordabilityBatch.execution_enabled.is_(False),
    ).update({"status": transition_batch("draft", "cancelled")}, synchronize_session=False)
    if not updated:
        db.rollback()
        batch = _load_company_batch(db, context.company_id, batch_id)
        if batch.status == "cancelled":
            return {"batch_id": str(batch.id), "status": "cancelled", "idempotent_replay": True}
        raise HTTPException(status_code=409, detail="Batch cannot be cancelled from its current state")
    db.commit()
    return {"batch_id": str(batch_id), "status": "cancelled", "idempotent_replay": False}
