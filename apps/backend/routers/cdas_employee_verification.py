from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_CEILING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_client import CompanyBorrowerAccount
from database.models.enums import LoanStatus
from database.session import get_db
from integrations.cdas import CdasError
from services.cdas_collection_policy import cdas_payroll_timing
from services.cdas_config_service import get_company_cdas_client
from services.cdas_deduction_lifecycle import _utcnow, _value, get_official_mandate_for_loan
from services.cdas_exact_identity import (
    CdasExactIdentityError,
    ResolvedCdasBorrower,
    mask_national_id,
    resolve_company_borrower_by_national_id,
    upsert_exact_verified_payroll_profile,
    validate_exact_provider_identity,
)


router = APIRouter(prefix="/cdas", tags=["CDAS Employee Verification"])
_ELIGIBLE_LOAN_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}
_MONEY_QUANTUM = Decimal("0.01")


class CdasEmployeeVerificationRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)


class CdasExactEmployeeVerificationRequest(BaseModel):
    national_id: str = Field(min_length=1, max_length=100)
    employee_no: str = Field(min_length=1, max_length=100)


class CdasOriginationPreviewRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)
    total_repayable: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    scheduled_installment: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    requested_term: int = Field(gt=0, le=120)


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(_MONEY_QUANTUM)
    except Exception:
        return Decimal("0.00")


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


def _add_months(anchor: date, months: int) -> date:
    month_index = (anchor.month - 1) + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _ceil_installments(total: Decimal, deduction: Decimal) -> int | None:
    if deduction <= 0:
        return None
    return int((total / deduction).to_integral_value(rounding=ROUND_CEILING))


def net_cdas_capacity(*, provider_affordability: object, pending_commitments: object) -> Decimal:
    """Return capacity not already reserved by LoanHub but not yet visible to CDAS."""
    provider = max(_money(provider_affordability), Decimal("0.00"))
    reserved = max(_money(pending_commitments), Decimal("0.00"))
    return max(provider - reserved, Decimal("0.00")).quantize(_MONEY_QUANTUM)


def _pending_cdas_commitments(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
) -> tuple[Decimal, list[dict[str, object]]]:
    """Reserve explicit CDAS loans not yet reflected in provider affordability.

    Once a loan has an official CDAS mandate, the provider's affordability is
    expected to reflect it, so LoanHub must not subtract that loan a second time.
    """
    loans = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.company_id == company_id,
            ClientCompanyLoan.borrower_id == borrower_id,
            ClientCompanyLoan.cdas_collection_enabled.is_(True),
            ClientCompanyLoan.status.in_(tuple(_ELIGIBLE_LOAN_STATUSES)),
            ClientCompanyLoan.balance > 0,
        )
        .all()
    )
    total = Decimal("0.00")
    reservations: list[dict[str, object]] = []
    for loan in loans:
        if get_official_mandate_for_loan(db, company_id=company_id, loan_id=loan.id) is not None:
            continue
        commitment = min(max(_money(loan.installment_amount), Decimal("0.00")), max(_money(loan.balance), Decimal("0.00")))
        if commitment <= 0:
            continue
        total += commitment
        reservations.append(
            {
                "loan_id": str(loan.id),
                "loan_reference": loan.loan_reference,
                "reserved_installment": float(commitment),
            }
        )
    return total.quantize(_MONEY_QUANTUM), reservations


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
async def preview_cdas_for_new_loan(
    borrower_id: UUID,
    payload: CdasOriginationPreviewRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Verify a borrower's CDAS payroll identity and return a read-only loan preview.

    The endpoint deliberately performs no deduction registration or lifecycle
    mutation. It binds the verified employee number to the borrower, reads live
    affordability, subtracts LoanHub CDAS commitments that have not yet reached
    the provider, and explains how the proposed repayment compares with the net
    payroll capacity. The normal monthly automation remains responsible for the
    actual provider lifecycle after the loan is originated.
    """
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
        provider_affordability = Decimal(str(await client.affordability(payload.employee_no.strip()) or 0)).quantize(_MONEY_QUANTUM)
    except CdasError as exc:
        status = exc.status_code if 400 <= exc.status_code <= 599 else 502
        raise HTTPException(
            status_code=status,
            detail={"provider": "CDAS", "code": exc.status_code, "message": exc.message},
        ) from exc

    provider_affordability = max(provider_affordability, Decimal("0.00"))
    pending_commitments, reservations = _pending_cdas_commitments(
        db,
        company_id=context.company_id,
        borrower_id=borrower_id,
    )
    affordability = net_cdas_capacity(
        provider_affordability=provider_affordability,
        pending_commitments=pending_commitments,
    )
    total_repayable = Decimal(payload.total_repayable).quantize(_MONEY_QUANTUM)
    scheduled_installment = Decimal(payload.scheduled_installment).quantize(_MONEY_QUANTUM)
    usable_scheduled = min(scheduled_installment, affordability) if affordability > 0 else Decimal("0.00")
    estimated_installments = _ceil_installments(total_repayable, usable_scheduled)
    fastest_installments = _ceil_installments(total_repayable, affordability)

    timing = cdas_payroll_timing(_utcnow())
    effective_year, effective_month = [int(value) for value in timing["effective_month"].split("-")]
    first_collection = date(effective_year, effective_month, 1)
    estimated_settlement_month = (
        _add_months(first_collection, max(estimated_installments - 1, 0)).strftime("%Y-%m")
        if estimated_installments
        else None
    )
    fastest_settlement_month = (
        _add_months(first_collection, max(fastest_installments - 1, 0)).strftime("%Y-%m")
        if fastest_installments
        else None
    )
    fits_scheduled_installment = affordability >= scheduled_installment

    return {
        **verification,
        "provider_reported_affordability": float(provider_affordability),
        "pending_loanhub_cdas_commitments": float(pending_commitments),
        "pending_commitment_loans": reservations,
        "affordability": float(affordability),
        "net_available_affordability": float(affordability),
        "total_repayable": float(total_repayable),
        "scheduled_installment": float(scheduled_installment),
        "requested_term": payload.requested_term,
        "fits_scheduled_installment": fits_scheduled_installment,
        "payroll_shortfall": float(max(scheduled_installment - affordability, Decimal("0.00"))),
        "remaining_affordability_after_scheduled": float(max(affordability - scheduled_installment, Decimal("0.00"))),
        "effective_preview_deduction": float(usable_scheduled),
        "estimated_installments_at_effective_deduction": estimated_installments,
        "estimated_settlement_month": estimated_settlement_month,
        "fastest_installments_at_full_affordability": fastest_installments,
        "fastest_settlement_month": fastest_settlement_month,
        "processing_window_start": timing["processing_window_start"],
        "processing_window_end": timing["processing_window_end"],
        "processing_time": timing["processing_time"],
        "timezone": timing["timezone"],
        "effective_month": timing["effective_month"],
        "first_expected_collection_month": timing["first_expected_collection_month"],
        "monitoring_required": affordability <= 0,
        "automation_note": (
            "No net payroll capacity is currently available after LoanHub pending CDAS commitments. The verified employee number is retained and monthly automation can monitor future capacity."
            if affordability <= 0
            else "This is a read-only origination preview using net CDAS capacity after LoanHub pending reservations. No CDAS deduction has been registered yet."
        ),
    }
