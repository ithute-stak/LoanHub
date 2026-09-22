from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.borrower import Borrower
from database.models.company_client import CompanyBorrowerAccount
from database.models.lending_operations import CDASPayrollProfile
from database.session import get_db
from integrations.cdas import CdasError
from services.cdas_config_service import get_company_cdas_client
from services.cdas_deduction_lifecycle import CdasLifecycleError, _utcnow, _value
from services.cdas_registration_workflow import _validate_employee_identity


router = APIRouter(prefix="/cdas", tags=["CDAS Employee Verification"])


class CdasEmployeeVerificationRequest(BaseModel):
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


@router.post("/borrowers/{borrower_id}/verify-employee")
async def verify_cdas_employee_for_borrower(
    borrower_id: UUID,
    payload: CdasEmployeeVerificationRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Verify one employee number against one known LoanHub borrower.

    This is the safe bootstrap for branch-scoped CDAS reads. It deliberately
    does not expose a general employee-number search: the CDAS identity must
    match the selected borrower's employee number, name, surname and date of
    birth before the payroll profile is marked officially verified.
    """
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, LENDING_ROLES)

    borrower = (
        db.query(Borrower)
        .filter(Borrower.id == borrower_id)
        .one_or_none()
    )
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found")

    account = _company_client_account(
        db,
        company_id=context.company_id,
        borrower_id=borrower_id,
    )
    _require_account_branch_scope(context, account)

    employee_no = payload.employee_no.strip()
    try:
        client = get_company_cdas_client(db, context.company_id)
        employee_details = await client.employee_details(employee_no)
    except CdasError as exc:
        status = exc.status_code if 400 <= exc.status_code <= 599 else 502
        raise HTTPException(
            status_code=status,
            detail={"provider": "CDAS", "code": exc.status_code, "message": exc.message},
        ) from exc

    try:
        _validate_employee_identity(
            SimpleNamespace(borrower=borrower),
            employee_no,
            employee_details,
        )
    except CdasLifecycleError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == context.company_id,
            CDASPayrollProfile.borrower_id == borrower_id,
        )
        .one_or_none()
    )
    if profile is None:
        profile = CDASPayrollProfile(
            company_id=context.company_id,
            borrower_id=borrower_id,
            branch_id=account.branch_id or context.branch_id,
            employee_number=employee_no,
        )
        db.add(profile)
    elif profile.employee_number.strip().casefold() != employee_no.casefold():
        raise HTTPException(
            status_code=409,
            detail="This borrower already has a different CDAS employee number on the payroll profile",
        )

    profile.branch_id = account.branch_id or context.branch_id
    profile.employee_number = employee_no
    profile.verified = True
    profile.verified_at = _utcnow()
    profile.verified_by_user_id = context.user.id
    profile.verification_reference = "CDAS_API_V1_5"
    profile.verification_notes = (
        "Employee number, name, surname and date of birth matched against the official CDAS employee endpoint."
    )
    db.commit()
    db.refresh(profile)

    return {
        "borrower_id": str(borrower_id),
        "employee_no": employee_no,
        "verified": True,
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
