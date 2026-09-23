from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_CEILING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.borrower import Borrower
from database.models.company_client import CompanyBorrowerAccount
from database.models.lending_operations import CDASPayrollProfile
from database.models.professional_lending import DirectLoanApplication
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
_MONEY_QUANTUM = Decimal("0.01")


class CdasEmployeeVerificationRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)


class CdasExactEmployeeVerificationRequest(BaseModel):
    national_id: str = Field(min_length=1, max_length=100)
    employee_no: str = Field(min_length=1, max_length=100)


class CdasOriginationPreviewRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)
    total_repayable: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    planned_installment: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    selected_term_count: int = Field(gt=0, le=120)
    first_payment_date: date | None = None


class CdasApplicationCollectionLinkRequest(BaseModel):
    enabled: bool
    employee_no: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_employee_number(self):
        if self.enabled and not str(self.employee_no or "").strip():
            raise ValueError("Enter and verify the CDAS employee number before enabling payroll collection")
        return self


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(_MONEY_QUANTUM)
    except Exception:
        return Decimal("0.00")


def _add_months(value: date, months: int) -> date:
    absolute_month = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(absolute_month, 12)
    month = month_index + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def calculate_cdas_origination_plan(
    *,
    total_repayable: object,
    affordability: object,
    planned_installment: object,
    selected_term_count: int,
    first_payment_date: date | None,
) -> dict[str, object]:
    """Calculate the live payroll-collection view shown during origination.

    CDAS affordability is treated as the maximum currently available payroll
    deduction.  The preview intentionally uses the full available capacity,
    capped at the debt, because the monthly automation may shorten the loan term
    when payroll capacity is higher than the contractual installment.
    """

    total = max(_money(total_repayable), Decimal("0.00"))
    available = max(_money(affordability), Decimal("0.00"))
    planned = max(_money(planned_installment), Decimal("0.00"))
    if total <= 0:
        raise ValueError("Total repayable must be positive")
    if planned <= 0:
        raise ValueError("Planned installment must be positive")
    if selected_term_count <= 0:
        raise ValueError("Selected term must be positive")

    proposed_deduction = min(total, available)
    if proposed_deduction <= 0:
        return {
            "available_affordability": available,
            "proposed_monthly_deduction": Decimal("0.00"),
            "estimated_installments": None,
            "estimated_settlement_date": None,
            "final_installment": None,
            "planned_installment": planned,
            "planned_installment_covered": False,
            "selected_term_count": selected_term_count,
            "within_selected_term": False,
            "status": "no_capacity",
            "message": "No CDAS affordability is available now. The loan can stay linked and the monthly automation will monitor for capacity.",
        }

    installments = int((total / proposed_deduction).to_integral_value(rounding=ROUND_CEILING))
    if installments > 600:
        raise ValueError("Calculated CDAS term exceeds the 600-installment safety limit")
    final_installment = total - (proposed_deduction * (installments - 1))
    settlement_date = _add_months(first_payment_date, installments - 1) if first_payment_date else None
    within_selected_term = installments <= selected_term_count
    planned_covered = available >= planned

    return {
        "available_affordability": available,
        "proposed_monthly_deduction": proposed_deduction,
        "estimated_installments": installments,
        "estimated_settlement_date": settlement_date,
        "final_installment": final_installment,
        "planned_installment": planned,
        "planned_installment_covered": planned_covered,
        "selected_term_count": selected_term_count,
        "within_selected_term": within_selected_term,
        "status": "within_selected_term" if within_selected_term else "longer_than_selected_term",
        "message": (
            f"Current CDAS affordability can clear the loan in about {installments} payroll installment(s)."
            if within_selected_term
            else f"Current CDAS affordability would take about {installments} payroll installment(s), longer than the selected {selected_term_count}-month term."
        ),
    }


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


def _application_for_company(
    db: Session,
    *,
    context: TenantContext,
    application_id: UUID,
) -> DirectLoanApplication:
    assert context.company_id is not None
    application = (
        db.query(DirectLoanApplication)
        .filter(
            DirectLoanApplication.id == application_id,
            DirectLoanApplication.company_id == context.company_id,
        )
        .one_or_none()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Loan application not found")
    if context.branch_id and application.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="The loan application is outside the active branch")
    return application


def _verified_payroll_profile(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
    employee_no: str,
) -> CDASPayrollProfile | None:
    return (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == company_id,
            CDASPayrollProfile.borrower_id == borrower_id,
            CDASPayrollProfile.employee_number == employee_no,
            CDASPayrollProfile.verified.is_(True),
        )
        .one_or_none()
    )


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


@router.post("/borrowers/{borrower_id}/origination-preview")
async def preview_cdas_collection_for_new_loan(
    borrower_id: UUID,
    payload: CdasOriginationPreviewRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Verify the employee, read live affordability and calculate payroll term."""
    _require_company_lending_member(context)
    assert context.company_id is not None

    borrower = db.query(Borrower).filter(Borrower.id == borrower_id).one_or_none()
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found")
    account = _company_client_account(db, company_id=context.company_id, borrower_id=borrower_id)
    person = getattr(getattr(borrower, "user", None), "person", None)
    if person is None or not str(getattr(person, "national_id", "") or "").strip():
        raise HTTPException(status_code=422, detail="The LoanHub client must have a National ID before CDAS can be linked")

    resolved = ResolvedCdasBorrower(borrower=borrower, account=account, person=person)
    verification = await _verify_resolved_employee(
        db,
        context=context,
        resolved=resolved,
        employee_no=payload.employee_no,
    )

    try:
        client = get_company_cdas_client(db, context.company_id)
        affordability = max(_money(await client.affordability(payload.employee_no.strip())), Decimal("0.00"))
    except CdasError as exc:
        status = exc.status_code if 400 <= exc.status_code <= 599 else 502
        raise HTTPException(
            status_code=status,
            detail={"provider": "CDAS", "code": exc.status_code, "message": exc.message},
        ) from exc

    try:
        plan = calculate_cdas_origination_plan(
            total_repayable=payload.total_repayable,
            affordability=affordability,
            planned_installment=payload.planned_installment,
            selected_term_count=payload.selected_term_count,
            first_payment_date=payload.first_payment_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "borrower_id": str(borrower_id),
        "employee_no": payload.employee_no.strip(),
        "verified": True,
        "verification": verification,
        "total_repayable": _money(payload.total_repayable),
        **plan,
    }


@router.get("/origination/applications/{application_id}/collection-link")
def get_application_cdas_collection_link(
    application_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_lending_member(context)
    application = _application_for_company(db, context=context, application_id=application_id)
    return {
        "application_id": str(application.id),
        "enabled": application.cdas_collection_enabled is True,
        "legacy_unspecified": application.cdas_collection_enabled is None,
        "employee_no": application.cdas_employee_number,
        "linked_at": application.cdas_linked_at.isoformat() if application.cdas_linked_at else None,
    }


@router.put("/origination/applications/{application_id}/collection-link")
def set_application_cdas_collection_link(
    application_id: UUID,
    payload: CdasApplicationCollectionLinkRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Persist the explicit per-loan CDAS collection choice made in origination."""
    _require_company_lending_member(context)
    assert context.company_id is not None
    application = _application_for_company(db, context=context, application_id=application_id)
    if application.status not in {"draft", "submitted", "under_review"}:
        raise HTTPException(status_code=409, detail="CDAS collection can only be changed before the loan decision is final")

    cleaned_employee_no = str(payload.employee_no or "").strip() or None
    if payload.enabled:
        assert cleaned_employee_no is not None
        profile = _verified_payroll_profile(
            db,
            company_id=context.company_id,
            borrower_id=application.borrower_id,
            employee_no=cleaned_employee_no,
        )
        if profile is None:
            raise HTTPException(
                status_code=409,
                detail="Verify this CDAS employee number against the borrower before enabling payroll collection",
            )
        if context.branch_id and profile.branch_id and profile.branch_id != context.branch_id:
            raise HTTPException(status_code=403, detail="The verified CDAS employee profile is outside the active branch")
        application.cdas_collection_enabled = True
        application.cdas_employee_number = cleaned_employee_no
    else:
        application.cdas_collection_enabled = False
        application.cdas_employee_number = None

    application.cdas_linked_at = _utcnow()
    application.cdas_linked_by_user_id = context.user.id
    db.commit()
    db.refresh(application)
    return {
        "application_id": str(application.id),
        "enabled": application.cdas_collection_enabled is True,
        "legacy_unspecified": False,
        "employee_no": application.cdas_employee_number,
        "linked_at": application.cdas_linked_at.isoformat() if application.cdas_linked_at else None,
    }
