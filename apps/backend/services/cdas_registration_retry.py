from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cdas_official import CdasOfficialMandateEvent, CdasOfficialMandateState
from integrations.cdas import CdasClient, CdasError
from services.cdas_deduction_lifecycle import (
    CdasLifecycleError,
    _apply_provider_response,
    _effective_month_start,
    _ensure_environment,
    _mark_uncertain_failure,
    _record_event,
    get_official_mandate,
    serialize_official_mandate,
)


_RETRYABLE_LOCAL_STATUSES = {"registration_pending", "registration_failed"}
_UNCERTAIN_PROVIDER_STATUSES = {401, 402}


def _provider_failure_is_safe_to_retry(status_code: int | None) -> bool:
    """Return True only when the prior provider rejection is known to be final.

    Authentication expiry and 5xx/network-style failures can leave the caller
    unsure whether CDAS applied the write, so those cases must be reconciled
    rather than replayed. Documented 4xx validation/rate-limit responses are
    treated as definitive rejections and may be corrected and resubmitted.
    """
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
    mandate.monthly_deduction = deduction_amount
    mandate.start_date = start_date
    mandate.expected_installments = total_installment
    mandate.total_expected = deduction_amount * Decimal(total_installment)
    mandate.external_reference = cleaned_reference
    mandate.status = "registration_retry_pending"

    state.item_code = item_code.strip()
    state.reference_no = cleaned_reference
    state.loan_policy = loan_policy
    state.principal_amount = principal_amount
    state.effective_month = effective_month.strip()
    state.last_request_type = 1
    state.last_error = None
    # Mark the state uncertain before the external write. If the worker dies
    # after CDAS receives the request but before LoanHub stores the response,
    # the persisted state safely forces reconciliation rather than replay.
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

    _apply_provider_response(state, mandate, response, requested_lifecycle="registered")
    _record_event(
        db,
        state=state,
        actor_user_id=actor_user_id,
        event_type="registration_retry",
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
