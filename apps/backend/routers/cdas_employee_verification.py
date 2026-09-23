from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.borrower import Borrower
from database.models.company_client import CompanyBorrowerAccount
from database.session import get_db
from integrations.cdas import CdasError
from services.cdas_config_service import get_company_cdas_client
from services.cdas_deduction_lifecycle import _utcnow, _value
from services.cdas_exact_identity import (
    CdasExactIdentityError,
    ResolvedCdasBorrower,
    mask_national_id,
    resolve_company_borrower_by_national_id,
    upsert_exact_verified_payroll_profile,
    validate_exact_provider_identity,
)


router = APIRouter(prefix="/cdas", tags=["CDAS Employee Verification"])


class CdasEmployeeVerificationRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)


class CdasExactEmployeeVerificationRequest(BaseModel):
    national_id: str = Field(min_length=1, max_length=100)
    employee_no: str = Field(min_length=1, max_length=100)


def _company_client_account(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
) -> CompanyBorrowerAccount:
    row = (
        db.query(CompanyBorrowerAccount)
        .filter(
            CompanyBorrowerAccount.company_id == company_id,
            CompanyBorrowerAccount.borrower_id == borrower_id,
            CompanyBorrowerAccount.status == "active",
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=409, detail="The borrower must be an active company client")
    return row


def _require_account_branch_scope(context: TenantContext, account: CompanyBorrowerAccount) -> None:
    if context.branch_id and account.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="The selected borrower is outside the active branch")


def _require_company_lending_member(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, LENDING_ROLES)


def _identity_http_error(exc: CdasExactIdentityError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def _verify_resolved_employee(
    db: Session,
    *,
    context: TenantContext,
    resolved: ResolvedCdasBorrower,
    employee_no: str,
) -> dict[str, object]:
    assert context.company_id is not None
    _require_account_branch_scope(context, resolved.account)

    cleaned_employee_no = employee_no.strip()
    try:
        client = get_company_cdas_client(db, context.company_id)
        employee_details = await client.employee_details(cleaned_employee_no)
    except CdasError as exc:
        status = exc.status_code if 400 <= exc.status_code <= 599 else 502
        raise HTTPException(
            status_code=status,
            detail={"provider": "CDAS", "code": exc.status_code, "message": exc.message},
        ) from exc

    try:
        identity = validate_exact_provider_identity(
            loanhub_national_id=str(resolved.person.national_id or ""),
            requested_employee_no=cleaned_employee_no,
            employee_details=employee_details,
        )
        profile = upsert_exact_verified_payroll_profile(
            db,
            company_id=context.company_id,
            borrower_id=resolved.borrower.id,
            branch_id=resolved.account.branch_id or context.branch_id,
            employee_no=cleaned_employee_no,
            verified_by_user_id=context.user.id,
            identity_metadata=identity,
            verified_at=_utcnow(),
        )
    except CdasExactIdentityError as exc:
        raise _identity_http_error(exc) from exc

    db.commit()
    db.refresh(profile)

    return {
        "borrower_id": str(resolved.borrower.id),
        "account_id": str(resolved.account.id),
        "account_reference": resolved.account.account_reference,
        "national_id_masked": mask_national_id(resolved.person.national_id),
        "employee_no": cleaned_employee_no,
        "verified": True,
        "identity_basis": identity["basis"],
        "provider_national_id_present": identity["provider_national_id_present"],
        "verification_reference": profile.verification_reference,
        "verified_at": profile.verified_at.isoformat() if profile.verified_at else None,
        "employee": {
            "employee_no": _value(employee_details, "EmployeeNo", "employeeNo", "employee_no"),
            "name": _value(employee_details, "Name", "name"),
            "surname": _value(employee_details, "Surname", "surname"),
            "dob": _value(employee_details, "DOB", "DateOfBirth", "dateOfBirth", "date_of_birth"),
            "department": _value(employee_details, "Department", "department"),
            "joining_date": _value(employee_details, "JoiningDate", "joiningDate", "joining_date"),
            "termination_date": _value(employee_details, "TerminationDate", "terminationDate", "termination_date"),
        },
    }


@router.post("/verify-employee")
async def verify_cdas_employee_by_national_id(
    payload: CdasExactEmployeeVerificationRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Bind CDAS EmployeeNo to exactly one active LoanHub client by National ID.

    National ID is the LoanHub identity key. EmployeeNo is the documented CDAS
    payroll key. Names and date of birth are display data only and are never used
    as an automatic identity fallback.
    """
    _require_company_lending_member(context)
    assert context.company_id is not None

    try:
        resolved = resolve_company_borrower_by_national_id(
            db,
            company_id=context.company_id,
            national_id=payload.national_id,
        )
    except CdasExactIdentityError as exc:
        raise _identity_http_error(exc) from exc

    return await _verify_resolved_employee(
        db,
        context=context,
        resolved=resolved,
        employee_no=payload.employee_no,
    )


@router.post("/borrowers/{borrower_id}/verify-employee")
async def verify_cdas_employee_for_borrower(
    borrower_id: UUID,
    payload: CdasEmployeeVerificationRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Backward-compatible UUID route using the same exact-identifier policy."""
    _require_company_lending_member(context)
    assert context.company_id is not None

    borrower = db.query(Borrower).filter(Borrower.id == borrower_id).one_or_none()
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found")

    account = _company_client_account(
        db,
        company_id=context.company_id,
        borrower_id=borrower_id,
    )
    person = getattr(getattr(borrower, "user", None), "person", None)
    if person is None or not str(getattr(person, "national_id", "") or "").strip():
        raise HTTPException(
            status_code=422,
            detail="The LoanHub client must have a National ID before CDAS can be linked",
        )

    resolved = ResolvedCdasBorrower(borrower=borrower, account=account, person=person)
    return await _verify_resolved_employee(
        db,
        context=context,
        resolved=resolved,
        employee_no=payload.employee_no,
    )
