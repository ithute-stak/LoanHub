from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cdas_official import CdasOfficialMandateState
from database.models.client_loan_company import ClientCompanyLoan
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
    get_official_mandate_for_loan,
    serialize_official_mandate,
)


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
    """Register a loan deduction with a durable uncertain-before-write marker.

    The local loan/mandate link is committed before the external call. Crucially,
    the state is persisted as reconciliation-required *before* CDAS receives the
    mutation. If the application process dies after submission but before it can
    store the response, a later user cannot mistake that state for a safe retry.
    """
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

    existing = get_official_mandate_for_loan(db, company_id=company_id, loan_id=loan_id)
    if existing is not None:
        raise CdasLifecycleError(409, "This LoanHub loan already has an official CDAS mandate")

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
    cleaned_employee_no = employee_no.strip()
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
            verified=False,
        )
        db.add(profile)
        db.flush()
    elif profile.employee_number != cleaned_employee_no:
        raise CdasLifecycleError(
            409,
            "The supplied employee number does not match this borrower's existing CDAS payroll profile",
        )

    start_date = _effective_month_start(effective_month)
    cleaned_reference = reference_no.strip()
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
        monthly_deduction=deduction_amount,
        start_date=start_date,
        expected_installments=total_installment,
        total_expected=deduction_amount * Decimal(total_installment),
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
        principal_amount=principal_amount,
        effective_month=effective_month.strip(),
        lifecycle_status="registration_submission_pending",
        last_request_type=1,
        requires_reconciliation=True,
        last_error="Registration submitted to CDAS; provider result has not yet been confirmed",
    )
    db.add(state)
    db.commit()
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

    _apply_provider_response(state, mandate, response, requested_lifecycle="registered")
    _record_event(
        db,
        state=state,
        actor_user_id=actor_user_id,
        event_type="registration",
        request_type=1,
        request_snapshot=request_payload,
        response_snapshot=response,
        provider_status_code=200,
        success=True,
    )
    db.commit()
    db.refresh(state)
    db.refresh(mandate)
    return serialize_official_mandate(state, mandate)
