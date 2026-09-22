from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models.cdas_official import CdasOfficialMandateState
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, RepaymentType
from database.models.lending_operations import CDASDeductionMandate, CDASPayrollProfile
from database.models.professional_lending import DirectLoanApplication
from integrations.cdas import CdasClient, CdasError
from services.cdas_deduction_lifecycle import (
    CdasLifecycleError,
    _apply_provider_response,
    _configuration_environment,
    _effective_month_start,
    _mark_uncertain_failure,
    _record_event,
    _utcnow,
    _value,
    get_official_mandate_for_loan,
    serialize_official_mandate,
)


_MONEY_QUANTUM = Decimal("0.01")


def _money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(_MONEY_QUANTUM)


def _normalized_name(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().replace("-", " ").split())


def _parse_cdas_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    iso_candidate = text[:10]
    try:
        return date.fromisoformat(iso_candidate)
    except ValueError:
        pass
    for pattern in ("%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _validate_loan_terms(
    loan: ClientCompanyLoan,
    *,
    branch_id: UUID | None,
    deduction_amount: Decimal,
    principal_amount: Decimal,
    total_installment: int,
    effective_month: str,
) -> None:
    if branch_id and loan.branch_id != branch_id:
        raise CdasLifecycleError(403, "The selected loan is outside the active branch")
    if loan.status not in {LoanStatus.APPROVED, LoanStatus.ACTIVE}:
        raise CdasLifecycleError(409, "Only an approved or active LoanHub loan can be registered in CDAS")
    if loan.repayment_type != RepaymentType.MONTHLY:
        raise CdasLifecycleError(422, "CDAS payroll registration requires a monthly LoanHub repayment schedule")
    if _money(deduction_amount) != _money(loan.installment_amount):
        raise CdasLifecycleError(422, "CDAS deduction amount must match the LoanHub loan installment amount")
    if _money(principal_amount) != _money(loan.principal_amount):
        raise CdasLifecycleError(422, "CDAS principal amount must match the LoanHub loan principal")
    if total_installment != int(loan.repayment_period):
        raise CdasLifecycleError(422, "CDAS installment count must match the LoanHub repayment period")

    start_date = _effective_month_start(effective_month)
    current_month = _utcnow().date().replace(day=1)
    if start_date < current_month:
        raise CdasLifecycleError(422, "CDAS effective month cannot be in the past")


def _validate_employee_identity(loan: ClientCompanyLoan, employee_no: str, payload: dict[str, object]) -> None:
    borrower = getattr(loan, "borrower", None)
    user = getattr(borrower, "user", None)
    person = getattr(user, "person", None)
    if person is None:
        raise CdasLifecycleError(422, "The borrower identity profile must be complete before CDAS registration")
    if not getattr(person, "date_of_birth", None):
        raise CdasLifecycleError(422, "The borrower's date of birth must be recorded before CDAS registration")

    provider_employee_no = str(_value(payload, "EmployeeNo", "employeeNo", "employee_no") or "").strip()
    provider_name = _normalized_name(_value(payload, "Name", "name"))
    provider_surname = _normalized_name(_value(payload, "Surname", "surname"))
    provider_dob = _parse_cdas_date(_value(payload, "DOB", "DateOfBirth", "dateOfBirth", "date_of_birth"))

    if not provider_employee_no or not provider_name or not provider_surname or provider_dob is None:
        raise CdasLifecycleError(502, "CDAS employee details are incomplete and cannot be safely linked to this borrower")
    if provider_employee_no.casefold() != employee_no.strip().casefold():
        raise CdasLifecycleError(409, "CDAS returned a different employee number than the one being registered")

    borrower_given_tokens = set(_normalized_name(getattr(person, "first_name", "")).split())
    borrower_surname = _normalized_name(getattr(person, "last_name", ""))
    provider_given_tokens = set(provider_name.split())
    if (
        not borrower_given_tokens
        or not borrower_given_tokens.issubset(provider_given_tokens)
        or borrower_surname != provider_surname
    ):
        raise CdasLifecycleError(409, "CDAS employee name does not match the LoanHub borrower identity")
    if provider_dob != person.date_of_birth:
        raise CdasLifecycleError(409, "CDAS employee date of birth does not match the LoanHub borrower identity")


async def register_loan_deduction_safely(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    branch_id: UUID | None,
    actor_user_id: UUID,
    loan_id: UUID,
    employee_no: str,
    item_code: str,
    reference_no: str,
    loan_policy: int,
    deduction_amount: Decimal,
    principal_amount: Decimal,
    total_installment: int,
    effective_month: str,
    borrower_consent: bool,
) -> dict[str, object]:
    """Register a loan deduction with identity, term and crash-safety controls."""
    if not borrower_consent:
        raise CdasLifecycleError(422, "Borrower consent must be confirmed before registering a CDAS deduction")
    if total_installment <= 0:
        raise CdasLifecycleError(422, "A CDAS loan deduction requires at least one installment")

    loan = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.id == loan_id, ClientCompanyLoan.company_id == company_id)
        .one_or_none()
    )
    if loan is None:
        raise CdasLifecycleError(404, "Loan was not found for this company")

    _validate_loan_terms(
        loan,
        branch_id=branch_id,
        deduction_amount=deduction_amount,
        principal_amount=principal_amount,
        total_installment=total_installment,
        effective_month=effective_month,
    )

    existing = get_official_mandate_for_loan(db, company_id=company_id, loan_id=loan_id)
    if existing is not None:
        raise CdasLifecycleError(409, "This LoanHub loan already has an official CDAS mandate")

    cleaned_employee_no = employee_no.strip()
    employee_details = await client.employee_details(cleaned_employee_no)
    _validate_employee_identity(loan, cleaned_employee_no, employee_details)

    live_affordability = Decimal(str(await client.affordability(cleaned_employee_no)))
    if _money(deduction_amount) > _money(live_affordability):
        raise CdasLifecycleError(
            422,
            "The LoanHub installment exceeds the current CDAS affordability for this employee",
        )

    application: DirectLoanApplication | None = None
    application_id = loan.direct_application_id
    if application_id:
        application = (
            db.query(DirectLoanApplication)
            .filter(
                DirectLoanApplication.id == application_id,
                DirectLoanApplication.company_id == company_id,
                DirectLoanApplication.borrower_id == loan.borrower_id,
            )
            .one_or_none()
        )

    environment = _configuration_environment(db, company_id)
    start_date = _effective_month_start(effective_month)
    cleaned_reference = reference_no.strip()

    # Reserve the local borrower/profile/loan/reference linkage before any CDAS
    # mutation. Database uniqueness is the final concurrency authority: if two
    # requests race after the preliminary checks, the losing transaction is
    # rolled back and reported as a controlled 409 instead of reaching CDAS.
    try:
        profile = (
            db.query(CDASPayrollProfile)
            .filter(
                CDASPayrollProfile.company_id == company_id,
                CDASPayrollProfile.borrower_id == loan.borrower_id,
            )
            .one_or_none()
        )
        if profile is None:
            profile = CDASPayrollProfile(
                company_id=company_id,
                borrower_id=loan.borrower_id,
                branch_id=branch_id or loan.branch_id,
                employee_number=cleaned_employee_no,
                verified=True,
                verified_at=_utcnow(),
                verified_by_user_id=actor_user_id,
                verification_reference="CDAS_API_V1_5",
                verification_notes="Employee number, name, surname and date of birth matched against the official CDAS employee endpoint.",
            )
            db.add(profile)
            db.flush()
        elif profile.employee_number.strip().casefold() != cleaned_employee_no.casefold():
            raise CdasLifecycleError(
                409,
                "The supplied employee number does not match this borrower's existing CDAS payroll profile",
            )
        else:
            profile.verified = True
            profile.verified_at = _utcnow()
            profile.verified_by_user_id = actor_user_id
            profile.verification_reference = "CDAS_API_V1_5"
            profile.verification_notes = "Employee number, name, surname and date of birth matched against the official CDAS employee endpoint."

        duplicate_reference = (
            db.query(CdasOfficialMandateState)
            .filter(
                CdasOfficialMandateState.company_id == company_id,
                CdasOfficialMandateState.environment == environment,
                CdasOfficialMandateState.reference_no == cleaned_reference,
            )
            .first()
        )
        if duplicate_reference is not None:
            raise CdasLifecycleError(409, "That CDAS reference number is already linked to another mandate")

        mandate = CDASDeductionMandate(
            company_id=company_id,
            branch_id=branch_id or loan.branch_id,
            borrower_id=loan.borrower_id,
            loan_id=loan.id,
            payroll_profile_id=profile.id,
            mandate_number=f"CDAS-{loan.loan_reference}"[:80],
            employee_number=cleaned_employee_no,
            monthly_deduction=_money(loan.installment_amount),
            start_date=start_date,
            expected_installments=int(loan.repayment_period),
            total_expected=_money(loan.installment_amount) * Decimal(int(loan.repayment_period)),
            status="registration_submission_pending",
            borrower_consent=True,
            external_reference=cleaned_reference,
            submitted_at=_utcnow(),
            created_by_user_id=actor_user_id,
        )
        db.add(mandate)
        db.flush()

        state = CdasOfficialMandateState(
            company_id=company_id,
            mandate_id=mandate.id,
            application_id=application.id if application else application_id,
            environment=environment,
            item_code=item_code.strip(),
            reference_no=cleaned_reference,
            loan_policy=loan_policy,
            principal_amount=_money(loan.principal_amount),
            effective_month=effective_month.strip(),
            lifecycle_status="registration_submission_pending",
            last_request_type=1,
            requires_reconciliation=True,
            last_error="Registration submitted to CDAS; provider result has not yet been confirmed",
        )
        db.add(state)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CdasLifecycleError(
            409,
            "This loan, borrower payroll profile, or CDAS reference is already linked or registration is already in progress",
        ) from exc

    db.refresh(state)
    db.refresh(mandate)

    request_payload = {
        "RequestType": 1,
        "DeductionID": 0,
        "EmployeeNo": mandate.employee_number,
        "LoanPolicy": state.loan_policy,
        "ItemCode": state.item_code,
        "DeductionAmount": float(mandate.monthly_deduction),
        "TotalInstallment": mandate.expected_installments,
        "PrincipalAmount": float(state.principal_amount),
        "EffectiveMonth": state.effective_month,
        "ReferenceNo": state.reference_no,
    }

    try:
        response = await client.add_update_deduction(request_payload)
    except CdasError as exc:
        _mark_uncertain_failure(state, exc)
        if not state.requires_reconciliation:
            state.lifecycle_status = "registration_failed"
            mandate.status = "registration_failed"
        _record_event(
            db,
            state=state,
            actor_user_id=actor_user_id,
            event_type="registration",
            request_type=1,
            request_snapshot=request_payload,
            provider_status_code=exc.status_code,
            success=False,
            message=exc.message,
        )
        db.commit()
        raise

    complete = _apply_provider_response(
        state,
        mandate,
        response,
        requested_lifecycle="registered",
        require_status=True,
        require_deduction_id=True,
    )
    _record_event(
        db,
        state=state,
        actor_user_id=actor_user_id,
        event_type="registration",
        request_type=1,
        request_snapshot=request_payload,
        response_snapshot=response,
        provider_status_code=200,
        success=complete,
        message=None if complete else state.last_error,
    )
    db.commit()
    db.refresh(state)
    db.refresh(mandate)
    if not complete:
        raise CdasLifecycleError(502, state.last_error or "CDAS returned an incomplete registration response")
    return serialize_official_mandate(state, mandate)
