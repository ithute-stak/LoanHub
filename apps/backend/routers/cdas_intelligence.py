from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.session import get_db
from integrations.cdas import CdasError
from services.cdas_analysis_history import save_or_get_analysis_record, serialize_analysis_record
from services.cdas_borrower_intelligence import build_borrower_loan_intelligence
from services.cdas_config_service import get_company_cdas_client
from services.cdas_deduction_lifecycle import CdasLifecycleError, _utcnow
from services.cdas_exact_identity import (
    CdasExactIdentityError,
    mask_national_id,
    resolve_company_borrower_by_national_id,
    upsert_exact_verified_payroll_profile,
    validate_exact_provider_identity,
)
from services.cdas_official_snapshot import normalize_official_cdas_snapshot
from services.cdas_registration_plan import build_cdas_registration_plan


router = APIRouter(prefix="/cdas", tags=["CDAS Borrower Intelligence"])


class CdasBorrowerIntelligenceRequest(BaseModel):
    national_id: str = Field(min_length=1, max_length=100)
    employee_no: str = Field(min_length=1, max_length=100)
    own_deduction_status: int | None = Field(default=None, ge=1, le=10)


def _require_lending_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, LENDING_ROLES)


def _identity_http_error(exc: CdasExactIdentityError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _cdas_http_error(exc: CdasError) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code <= 599 else 502
    return HTTPException(
        status_code=status,
        detail={"provider": "CDAS", "code": exc.status_code, "message": exc.message},
    )


def _report_preparer(context: TenantContext) -> tuple[str, str]:
    person = getattr(context.user, "person", None)
    prepared_by = (
        str(getattr(person, "full_name", "") or "").strip()
        or str(context.user.email or "").strip()
        or str(context.user.phone or "").strip()
        or "Authorized company user"
    )
    role = getattr(context.role, "value", None) or str(context.role)
    return prepared_by, str(role)


@router.get("/loans/{loan_id}/registration-plan")
def get_cdas_registration_plan(
    loan_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Prepare contract-safe fields for the official lifecycle without provider I/O."""
    _require_lending_member(context)
    assert context.company_id is not None
    try:
        return build_cdas_registration_plan(
            db,
            company_id=context.company_id,
            branch_id=context.branch_id,
            loan_id=loan_id,
        )
    except CdasLifecycleError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/intelligence")
async def run_cdas_borrower_intelligence(
    payload: CdasBorrowerIntelligenceRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Join live CDAS payroll capacity to LoanHub debt using exact National ID.

    This endpoint may establish the verified EmployeeNo-to-borrower link, so it
    is limited to lending-authorized staff. It never registers, changes, approves
    or settles a provider deduction; those mutations remain behind the official
    loan-linked lifecycle and borrower-consent controls.
    """
    _require_lending_member(context)
    assert context.company_id is not None

    try:
        resolved = resolve_company_borrower_by_national_id(
            db,
            company_id=context.company_id,
            national_id=payload.national_id,
        )
    except CdasExactIdentityError as exc:
        raise _identity_http_error(exc) from exc

    if context.branch_id and resolved.account.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="The matched LoanHub client is outside the active branch")

    employee_no = payload.employee_no.strip()
    try:
        client = get_company_cdas_client(db, context.company_id)
        raw_snapshot = await client.refresh_employee_snapshot(
            employee_no,
            own_deduction_status=payload.own_deduction_status,
        )
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc

    employee_details = raw_snapshot.get("employee")
    if not isinstance(employee_details, dict):
        raise HTTPException(status_code=502, detail="CDAS employee details returned an invalid response")

    try:
        identity = validate_exact_provider_identity(
            loanhub_national_id=str(resolved.person.national_id or ""),
            requested_employee_no=employee_no,
            employee_details=employee_details,
        )
        profile = upsert_exact_verified_payroll_profile(
            db,
            company_id=context.company_id,
            borrower_id=resolved.borrower.id,
            branch_id=resolved.account.branch_id or context.branch_id,
            employee_no=employee_no,
            verified_by_user_id=context.user.id,
            identity_metadata=identity,
            verified_at=_utcnow(),
        )
        db.commit()
        db.refresh(profile)
    except CdasExactIdentityError as exc:
        db.rollback()
        raise _identity_http_error(exc) from exc

    analysis = normalize_official_cdas_snapshot(
        raw_snapshot,
        own_deduction_status=payload.own_deduction_status,
    )
    affordability = (analysis.get("official_api") or {}).get("affordability", 0)
    loanhub = build_borrower_loan_intelligence(
        db,
        company_id=context.company_id,
        borrower_id=resolved.borrower.id,
        affordability=affordability,
    )

    profile_data = analysis.get("profile") or {}
    prepared_by, prepared_by_role = _report_preparer(context)
    record, created = save_or_get_analysis_record(
        db,
        company_id=context.company_id,
        analyzed_by_user_id=context.user.id,
        analyzed_by_name=prepared_by,
        analyzed_by_role=prepared_by_role,
        client_name=profile_data.get("full_name") or getattr(resolved.person, "full_name", None),
        client_reference=profile_data.get("employee_no") or employee_no,
        analysis=analysis,
    )

    return {
        "source": "CDAS_API",
        "checked_at": raw_snapshot.get("checked_at"),
        "identity": {
            "borrower_id": str(resolved.borrower.id),
            "account_id": str(resolved.account.id),
            "account_reference": resolved.account.account_reference,
            "client_name": getattr(resolved.person, "full_name", None),
            "national_id_masked": mask_national_id(resolved.person.national_id),
            "employee_no": employee_no,
            "verified": True,
            "basis": identity["basis"],
            "provider_national_id_present": identity["provider_national_id_present"],
        },
        "snapshot": analysis,
        "loanhub": loanhub,
        "archive": {"created": created, "record": serialize_analysis_record(record)},
    }
