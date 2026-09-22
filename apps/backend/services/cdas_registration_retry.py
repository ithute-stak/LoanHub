from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cdas_official import CdasOfficialMandateEvent, CdasOfficialMandateState
from database.models.client_loan_company import ClientCompanyLoan
from integrations.cdas import CdasClient, CdasError
from services.cdas_deduction_lifecycle import (
    CDAS_AUTH_UNCERTAIN_STATUSES,
    CdasLifecycleError,
    _apply_provider_response,
    _effective_month_start,
    _ensure_environment,
    _mark_uncertain_failure,
    _record_event,
    get_official_mandate,
    serialize_official_mandate,
)
from services.cdas_registration_workflow import (
    _money,
    _validate_employee_identity,
    _validate_loan_terms,
)


_RETRYABLE_LOCAL_STATUSES = {"registration_pending", "registration_failed"}
_UNCERTAIN_PROVIDER_STATUSES = set(CDAS_AUTH_UNCERTAIN_STATUSES)


def _provider_failure_is_safe_to_retry(status_code: int | None) -> bool:
    """Return True only when the prior provider rejection is known to be final."""
    if status_code is None:
        return False
    if status_code in _UNCERTAIN_PROVIDER_STATUSES:
        return False
    return status_code < 500


def _latest_failed_registration_event(
    db: Session,
    *,
    company_id: UUID,
    state_id: UUID,
) -> CdasOfficialMandateEvent | None:
    return (
        db.query(CdasOfficialMandateEvent)
        .filter(
            CdasOfficialMandateEvent.company_id == company_id,
            CdasOfficialMandateEvent.state_id == state_id,
            CdasOfficialMandateEvent.event_type.in_(["registration", "registration_retry"]),
            CdasOfficialMandateEvent.success.is_(False),
        )
        .order_by(CdasOfficialMandateEvent.occurred_at.desc())
        .first()
    )


async def retry_failed_registration(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    actor_user_id: UUID,
    state_id: UUID,
    item_code: str,
    reference_no: str,
    loan_policy: int,
    deduction_amount: Decimal,
    principal_amount: Decimal,
    total_installment: int,
    effective_month: str,
) -> dict[str, object]:
    state, mandate = get_official_mandate(db, company_id=company_id, state_id=state_id)
    _ensure_environment(db, state)

    current = str(state.lifecycle_status or "").strip().lower()
    if state.requires_reconciliation:
        raise CdasLifecycleError(
            409,
            "This registration has an uncertain CDAS result and must be reconciled before any retry",
        )
    if state.deduction_id is not None:
        raise CdasLifecycleError(409, "This mandate already has a CDAS deduction ID and cannot be re-registered")
    if current not in _RETRYABLE_LOCAL_STATUSES:
        raise CdasLifecycleError(409, f"A CDAS registration cannot be retried while the mandate is {current or 'unknown'}")

    previous_failure = _latest_failed_registration_event(
        db,
        company_id=company_id,
        state_id=state.id,
    )
    if previous_failure is None or not _provider_failure_is_safe_to_retry(previous_failure.provider_status_code):
        raise CdasLifecycleError(
            409,
            "LoanHub does not have a confirmed retry-safe CDAS rejection for this registration; reconcile it instead of replaying the write",
        )

    if total_installment <= 0:
        raise CdasLifecycleError(422, "A CDAS loan deduction requires at least one installment")

    loan = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.id == mandate.loan_id,
            ClientCompanyLoan.company_id == company_id,
        )
        .one_or_none()
    )
    if loan is None:
        raise CdasLifecycleError(404, "The linked LoanHub loan was not found")

    _validate_loan_terms(
        loan,
        branch_id=None,
        deduction_amount=deduction_amount,
        principal_amount=principal_amount,
        total_installment=total_installment,
        effective_month=effective_month,
    )

    employee_details = await client.employee_details(mandate.employee_number)
    _validate_employee_identity(loan, mandate.employee_number, employee_details)
    live_affordability = Decimal(str(await client.affordability(mandate.employee_number)))
    if _money(deduction_amount) > _money(live_affordability):
        raise CdasLifecycleError(
            422,
            "The LoanHub installment exceeds the current CDAS affordability for this employee",
        )

    cleaned_reference = reference_no.strip()
    duplicate_reference = (
        db.query(CdasOfficialMandateState)
        .filter(
            CdasOfficialMandateState.company_id == company_id,
            CdasOfficialMandateState.environment == state.environment,
            CdasOfficialMandateState.reference_no == cleaned_reference,
            CdasOfficialMandateState.id != state.id,
        )
        .first()
    )
    if duplicate_reference is not None:
        raise CdasLifecycleError(409, "That CDAS reference number is already linked to another mandate")

    start_date = _effective_month_start(effective_month)
    mandate.monthly_deduction = _money(loan.installment_amount)
    mandate.start_date = start_date
    mandate.expected_installments = int(loan.repayment_period)
    mandate.total_expected = _money(loan.installment_amount) * Decimal(int(loan.repayment_period))
    mandate.external_reference = cleaned_reference
    mandate.status = "registration_retry_pending"

    state.item_code = item_code.strip()
    state.reference_no = cleaned_reference
    state.loan_policy = loan_policy
    state.principal_amount = _money(loan.principal_amount)
    state.effective_month = effective_month.strip()
    state.last_request_type = 1
    state.last_error = None
    state.requires_reconciliation = True
    state.lifecycle_status = "registration_retry_pending"
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
            event_type="registration_retry",
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
        event_type="registration_retry",
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
