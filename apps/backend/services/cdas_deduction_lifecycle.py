from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cdas_official import CdasOfficialMandateEvent, CdasOfficialMandateState
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, RepaymentType
from database.models.lending_operations import CDASDeductionMandate
from integrations.cdas import CdasClient, CdasError
from services.cdas_config_service import get_configuration


# Provider responses that indicate token/session problems. State-changing calls
# are never replayed automatically for these codes; they require reconciliation.
CDAS_AUTH_UNCERTAIN_STATUSES = {401, 402, 406, 417, 419}


@dataclass(slots=True)
class CdasLifecycleError(Exception):
    status_code: int
    message: str

    def __str__(self) -> str:
        return self.message


def _utcnow() -> datetime:
    # LoanHub's existing DateTime columns are timezone-naive in PostgreSQL.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _value(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None
    exact = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        if key.lower() in exact:
            return exact[key.lower()]
    return None


def _to_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _effective_month_start(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise CdasLifecycleError(422, "effective_month must use YYYY-MM format") from exc


def _configuration_environment(db: Session, company_id: UUID) -> str:
    row = get_configuration(db, company_id)
    if row is None or not row.is_enabled:
        raise CdasLifecycleError(503, "CDAS is not enabled for this company")
    environment = str(row.environment or "test").strip().lower()
    if environment not in {"test", "live"}:
        raise CdasLifecycleError(503, "This company's CDAS environment is invalid")
    return environment


def _ensure_environment(db: Session, state: CdasOfficialMandateState) -> None:
    current = _configuration_environment(db, state.company_id)
    if current != state.environment:
        raise CdasLifecycleError(
            409,
            f"This mandate belongs to the {state.environment} CDAS environment; switch the company configuration back to that environment before changing it",
        )


def _lifecycle_from_code(code: int | None) -> str | None:
    return {
        1: "registered",
        2: "reserved",
        3: "reviewed",
        4: "approved",
        5: "active",
        6: "cancelled_or_rejected",
        7: "settled",
        8: "expired_or_auto_settled",
        9: "deleted",
        10: "changed",
    }.get(code)


def _lifecycle_from_request_type(request_type: int) -> str:
    return {
        1: "registered",
        3: "reviewed",
        4: "approved",
        5: "active",
        6: "cancelled_or_rejected",
        9: "deleted",
        10: "changed",
    }.get(request_type, "submitted")


def _set_lifecycle_timestamp(state: CdasOfficialMandateState, lifecycle: str, now: datetime) -> None:
    if lifecycle == "registered" and state.registered_at is None:
        state.registered_at = now
    elif lifecycle == "reviewed" and state.reviewed_at is None:
        state.reviewed_at = now
    elif lifecycle == "approved" and state.approved_at is None:
        state.approved_at = now
    elif lifecycle == "settled" and state.settled_at is None:
        state.settled_at = now
    elif lifecycle == "cancelled_or_rejected" and state.cancelled_at is None:
        state.cancelled_at = now


def _record_event(
    db: Session,
    *,
    state: CdasOfficialMandateState,
    actor_user_id: UUID | None,
    event_type: str,
    request_type: int | None,
    request_snapshot: dict[str, Any],
    response_snapshot: Any = None,
    provider_status_code: int | None = None,
    success: bool,
    message: str | None = None,
) -> None:
    db.add(
        CdasOfficialMandateEvent(
            company_id=state.company_id,
            state_id=state.id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            request_type=request_type,
            request_snapshot=request_snapshot,
            response_snapshot=(
                response_snapshot
                if isinstance(response_snapshot, dict)
                else {"value": response_snapshot}
                if response_snapshot is not None
                else {}
            ),
            provider_status_code=provider_status_code,
            success=success,
            message=message,
            occurred_at=_utcnow(),
        )
    )


def _mark_uncertain_failure(state: CdasOfficialMandateState, exc: CdasError) -> None:
    state.last_error = exc.message
    # Auth/session failures are deliberately not replayed for writes. Server or
    # network failures can also leave the caller unsure whether CDAS applied it.
    state.requires_reconciliation = (
        exc.status_code in CDAS_AUTH_UNCERTAIN_STATUSES or exc.status_code >= 500
    )
    if state.requires_reconciliation:
        state.lifecycle_status = "reconciliation_required"


def _apply_provider_response(
    state: CdasOfficialMandateState,
    mandate: CDASDeductionMandate,
    response: Any,
    *,
    requested_lifecycle: str,
    require_status: bool = False,
    require_deduction_id: bool = False,
) -> bool:
    """Apply a provider response and return whether it was structurally complete.

    CDAS v1.5 documents DeductionStatus on successful add/update/review/approve/
    cancel responses. Modify-active and settlement responses do not include that
    field, so their callers intentionally allow the requested lifecycle fallback.
    """
    now = _utcnow()
    deduction_id = _to_int(_value(response, "DeductionID", "DeductionId", "deduction_id"))
    status_code = _to_int(_value(response, "DeductionStatus", "Status", "deduction_status"))
    known_lifecycle = _lifecycle_from_code(status_code)

    if require_status and known_lifecycle is None:
        state.last_provider_response = response if isinstance(response, dict) else {"value": response}
        state.last_error = "CDAS returned a success response without a valid DeductionStatus"
        state.requires_reconciliation = True
        state.lifecycle_status = "reconciliation_required"
        state.last_synced_at = now
        return False
    if require_deduction_id and (deduction_id is None or deduction_id <= 0):
        state.last_provider_response = response if isinstance(response, dict) else {"value": response}
        state.last_error = "CDAS returned a registration response without a valid DeductionID"
        state.requires_reconciliation = True
        state.lifecycle_status = "reconciliation_required"
        state.last_synced_at = now
        return False

    if deduction_id is not None:
        state.deduction_id = deduction_id
    if status_code is not None:
        state.cdas_status = status_code
    lifecycle = known_lifecycle or requested_lifecycle
    state.lifecycle_status = lifecycle
    state.last_provider_response = response if isinstance(response, dict) else {"value": response}
    state.last_error = None
    state.requires_reconciliation = False
    state.last_synced_at = now
    _set_lifecycle_timestamp(state, lifecycle, now)

    mandate.status = lifecycle
    if lifecycle == "active" and mandate.activated_at is None:
        mandate.activated_at = now
    if lifecycle in {"settled", "deleted", "expired_or_auto_settled", "cancelled_or_rejected"}:
        mandate.completed_at = mandate.completed_at or now
    provider_reference = _value(response, "ReferenceNo", "ReferenceNumber", "reference_no")
    if provider_reference:
        mandate.external_reference = str(provider_reference)
    return True


def serialize_official_mandate(state: CdasOfficialMandateState, mandate: CDASDeductionMandate) -> dict[str, Any]:
    return {
        "id": str(state.id),
        "mandate_id": str(mandate.id),
        "company_id": str(state.company_id),
        "borrower_id": str(mandate.borrower_id),
        "loan_id": str(mandate.loan_id),
        "application_id": str(state.application_id) if state.application_id else None,
        "environment": state.environment,
        "employee_no": mandate.employee_number,
        "deduction_id": state.deduction_id,
        "item_code": state.item_code,
        "reference_no": state.reference_no,
        "loan_policy": state.loan_policy,
        "deduction_amount": float(mandate.monthly_deduction),
        "principal_amount": float(state.principal_amount),
        "total_installment": mandate.expected_installments,
        "effective_month": state.effective_month,
        "cdas_status": state.cdas_status,
        "lifecycle_status": state.lifecycle_status,
        "requires_reconciliation": state.requires_reconciliation,
        "last_error": state.last_error,
        "last_synced_at": state.last_synced_at.isoformat() if state.last_synced_at else None,
        "registered_at": state.registered_at.isoformat() if state.registered_at else None,
        "reviewed_at": state.reviewed_at.isoformat() if state.reviewed_at else None,
        "approved_at": state.approved_at.isoformat() if state.approved_at else None,
        "activated_at": mandate.activated_at.isoformat() if mandate.activated_at else None,
        "settled_at": state.settled_at.isoformat() if state.settled_at else None,
        "cancelled_at": state.cancelled_at.isoformat() if state.cancelled_at else None,
    }


def get_official_mandate_for_loan(
    db: Session,
    *,
    company_id: UUID,
    loan_id: UUID,
) -> tuple[CdasOfficialMandateState, CDASDeductionMandate] | None:
    return (
        db.query(CdasOfficialMandateState, CDASDeductionMandate)
        .join(CDASDeductionMandate, CDASDeductionMandate.id == CdasOfficialMandateState.mandate_id)
        .filter(
            CdasOfficialMandateState.company_id == company_id,
            CDASDeductionMandate.company_id == company_id,
            CDASDeductionMandate.loan_id == loan_id,
        )
        .one_or_none()
    )


def get_official_mandate(
    db: Session,
    *,
    company_id: UUID,
    state_id: UUID,
) -> tuple[CdasOfficialMandateState, CDASDeductionMandate]:
    row = (
        db.query(CdasOfficialMandateState, CDASDeductionMandate)
        .join(CDASDeductionMandate, CDASDeductionMandate.id == CdasOfficialMandateState.mandate_id)
        .filter(
            CdasOfficialMandateState.id == state_id,
            CdasOfficialMandateState.company_id == company_id,
            CDASDeductionMandate.company_id == company_id,
        )
        .one_or_none()
    )
    if row is None:
        raise CdasLifecycleError(404, "CDAS mandate was not found for this company")
    return row


def _linked_loan(db: Session, *, company_id: UUID, mandate: CDASDeductionMandate) -> ClientCompanyLoan:
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
    return loan


def _registration_actor(db: Session, state_id: UUID) -> UUID | None:
    event = (
        db.query(CdasOfficialMandateEvent)
        .filter(
            CdasOfficialMandateEvent.state_id == state_id,
            CdasOfficialMandateEvent.event_type.in_(["registration", "registration_retry"]),
            CdasOfficialMandateEvent.success.is_(True),
        )
        .order_by(CdasOfficialMandateEvent.occurred_at.desc())
        .first()
    )
    return event.actor_user_id if event else None


def _require_maker_checker(db: Session, *, state_id: UUID, actor_user_id: UUID, request_type: int) -> None:
    if request_type not in {3, 4, 5}:
        return
    maker = _registration_actor(db, state_id)
    if maker is not None and maker == actor_user_id:
        raise CdasLifecycleError(
            409,
            "The user who registered this CDAS deduction cannot review, approve or activate the same deduction",
        )


async def perform_linked_action(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    actor_user_id: UUID,
    state_id: UUID,
    request_type: int,
) -> dict[str, Any]:
    if request_type not in {3, 4, 5, 6, 9, 10}:
        raise CdasLifecycleError(422, "Use the dedicated register or settlement operation for this CDAS request type")
    state, mandate = get_official_mandate(db, company_id=company_id, state_id=state_id)
    _ensure_environment(db, state)
    if state.requires_reconciliation:
        raise CdasLifecycleError(409, "Reconcile this CDAS mandate before sending another state-changing request")
    if not state.deduction_id:
        raise CdasLifecycleError(409, "CDAS deduction ID is not known; reconcile the mandate before continuing")
    _require_maker_checker(
        db,
        state_id=state.id,
        actor_user_id=actor_user_id,
        request_type=request_type,
    )

    request_payload = {
        "RequestType": request_type,
        "DeductionID": state.deduction_id,
        "EmployeeNo": mandate.employee_number,
        "LoanPolicy": state.loan_policy,
        "ItemCode": state.item_code,
        "DeductionAmount": float(mandate.monthly_deduction),
        "TotalInstallment": mandate.expected_installments,
        "PrincipalAmount": float(state.principal_amount),
        "EffectiveMonth": state.effective_month,
        "ReferenceNo": state.reference_no,
    }
    state.last_request_type = request_type
    try:
        response = await client.add_update_deduction(request_payload)
    except CdasError as exc:
        _mark_uncertain_failure(state, exc)
        _record_event(
            db,
            state=state,
            actor_user_id=actor_user_id,
            event_type="lifecycle_action",
            request_type=request_type,
            request_snapshot=request_payload,
            provider_status_code=exc.status_code,
            success=False,
            message=exc.message,
        )
        db.commit()
        raise

    requested_lifecycle = _lifecycle_from_request_type(request_type)
    complete = _apply_provider_response(
        state,
        mandate,
        response,
        requested_lifecycle=requested_lifecycle,
        require_status=True,
    )
    _record_event(
        db,
        state=state,
        actor_user_id=actor_user_id,
        event_type="lifecycle_action",
        request_type=request_type,
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
        raise CdasLifecycleError(502, state.last_error or "CDAS returned an incomplete lifecycle response")
    return serialize_official_mandate(state, mandate)


async def modify_linked_active_deduction(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    actor_user_id: UUID,
    state_id: UUID,
    effective_date: str,
    deduction_amount: Decimal | None = None,
    principal_amount: Decimal | None = None,
    total_installment: int | None = None,
) -> dict[str, Any]:
    state, mandate = get_official_mandate(db, company_id=company_id, state_id=state_id)
    _ensure_environment(db, state)
    if state.requires_reconciliation:
        raise CdasLifecycleError(409, "Reconcile this CDAS mandate before modifying it")
    if not state.deduction_id:
        raise CdasLifecycleError(409, "CDAS deduction ID is not known; reconcile the mandate before continuing")

    loan = _linked_loan(db, company_id=company_id, mandate=mandate)
    if loan.status != LoanStatus.ACTIVE:
        raise CdasLifecycleError(409, "The linked LoanHub loan must be active before its active CDAS deduction can be changed")
    if loan.repayment_type != RepaymentType.MONTHLY:
        raise CdasLifecycleError(422, "CDAS active-deduction changes require a monthly LoanHub repayment schedule")

    loan_amount = _money(loan.installment_amount)
    loan_principal = _money(loan.principal_amount)
    loan_installments = int(loan.repayment_period)
    if deduction_amount is not None and _money(deduction_amount) != loan_amount:
        raise CdasLifecycleError(422, "CDAS deduction amount must match the current LoanHub installment amount")
    if principal_amount is not None and _money(principal_amount) != loan_principal:
        raise CdasLifecycleError(422, "CDAS principal amount must match the current LoanHub principal")
    if total_installment is not None and int(total_installment) != loan_installments:
        raise CdasLifecycleError(422, "CDAS installment count must match the current LoanHub repayment period")
    if loan_installments <= 0:
        raise CdasLifecycleError(422, "A CDAS loan deduction requires at least one installment")

    current_amount = _money(mandate.monthly_deduction)
    increase = max(loan_amount - current_amount, Decimal("0.00"))
    if increase > 0:
        available = _money(await client.affordability(mandate.employee_number))
        if increase > available:
            raise CdasLifecycleError(
                422,
                "The increase in the LoanHub installment exceeds the employee's current CDAS affordability",
            )

    request_payload = {
        "EmployeeNo": mandate.employee_number,
        "ItemCode": state.item_code,
        "TotalInstallment": loan_installments,
        "DeductionAmount": float(loan_amount),
        "PrincipalAmount": float(loan_principal),
        "DeductionID": state.deduction_id,
        "EffectiveDate": effective_date.strip(),
    }
    try:
        response = await client.modify_active_deduction(request_payload)
    except CdasError as exc:
        _mark_uncertain_failure(state, exc)
        _record_event(
            db,
            state=state,
            actor_user_id=actor_user_id,
            event_type="modify_active",
            request_type=10,
            request_snapshot=request_payload,
            provider_status_code=exc.status_code,
            success=False,
            message=exc.message,
        )
        db.commit()
        raise

    mandate.monthly_deduction = loan_amount
    mandate.expected_installments = loan_installments
    mandate.total_expected = loan_amount * Decimal(loan_installments)
    state.principal_amount = loan_principal
    state.last_request_type = 10
    _apply_provider_response(state, mandate, response, requested_lifecycle="changed")
    _record_event(
        db,
        state=state,
        actor_user_id=actor_user_id,
        event_type="modify_active",
        request_type=10,
        request_snapshot=request_payload,
        response_snapshot=response,
        provider_status_code=200,
        success=True,
    )
    db.commit()
    db.refresh(state)
    db.refresh(mandate)
    return serialize_official_mandate(state, mandate)


def _validate_settlement_against_loan(loan: ClientCompanyLoan, settlement_reason: int) -> None:
    if settlement_reason not in {1, 2, 3, 4}:
        raise CdasLifecycleError(422, "Unsupported CDAS settlement reason")

    # Paid-by-employee and consolidation mean the linked LoanHub debt should
    # already be extinguished/closed before payroll deductions are stopped.
    if settlement_reason in {2, 3}:
        balance = _money(loan.balance)
        if loan.status != LoanStatus.COMPLETED and balance > Decimal("0.00"):
            reason = "paid by employee" if settlement_reason == 2 else "consolidated"
            raise CdasLifecycleError(
                409,
                f"LoanHub still shows an outstanding balance; the CDAS deduction cannot be marked {reason} yet",
            )


async def settle_linked_deduction(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    actor_user_id: UUID,
    state_id: UUID,
    effective_date: str,
    settlement_reason: int,
) -> dict[str, Any]:
    state, mandate = get_official_mandate(db, company_id=company_id, state_id=state_id)
    _ensure_environment(db, state)
    if state.requires_reconciliation:
        raise CdasLifecycleError(409, "Reconcile this CDAS mandate before settling it")
    if not state.deduction_id:
        raise CdasLifecycleError(409, "CDAS deduction ID is not known; reconcile the mandate before continuing")

    loan = _linked_loan(db, company_id=company_id, mandate=mandate)
    _validate_settlement_against_loan(loan, settlement_reason)

    request_payload = {
        "ItemCode": state.item_code,
        "DeductionID": state.deduction_id,
        "EffectiveDate": effective_date.strip(),
        "EmployeeNo": mandate.employee_number,
        "SettlementReason": settlement_reason,
    }
    try:
        response = await client.settle_deduction(request_payload)
    except CdasError as exc:
        _mark_uncertain_failure(state, exc)
        _record_event(
            db,
            state=state,
            actor_user_id=actor_user_id,
            event_type="settlement",
            request_type=7,
            request_snapshot=request_payload,
            provider_status_code=exc.status_code,
            success=False,
            message=exc.message,
        )
        db.commit()
        raise

    state.last_request_type = 7
    _apply_provider_response(state, mandate, response, requested_lifecycle="settled")
    _record_event(
        db,
        state=state,
        actor_user_id=actor_user_id,
        event_type="settlement",
        request_type=7,
        request_snapshot=request_payload,
        response_snapshot=response,
        provider_status_code=200,
        success=True,
    )
    db.commit()
    db.refresh(state)
    db.refresh(mandate)
    return serialize_official_mandate(state, mandate)


async def reconcile_linked_deduction(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    actor_user_id: UUID,
    state_id: UUID,
    deduction_status: int,
) -> dict[str, Any]:
    state, mandate = get_official_mandate(db, company_id=company_id, state_id=state_id)
    _ensure_environment(db, state)
    items = await client.own_deductions(mandate.employee_number, deduction_status)

    matches: list[dict[str, Any]] = []
    for item in items:
        item_id = _to_int(_value(item, "DeductionID", "DeductionId", "deduction_id"))
        item_reference = _value(item, "ReferenceNo", "ReferenceNumber", "reference_no")
        if state.deduction_id and item_id == state.deduction_id:
            matches.append(item)
        elif item_reference is not None and str(item_reference).strip() == state.reference_no:
            matches.append(item)

    if not matches:
        raise CdasLifecycleError(404, "No matching company CDAS deduction was found for this mandate and status")
    if len(matches) > 1:
        raise CdasLifecycleError(409, "CDAS returned more than one deduction matching this LoanHub mandate")

    match = matches[0]
    now = _utcnow()
    provider_id = _to_int(_value(match, "DeductionID", "DeductionId", "deduction_id"))
    provider_status = _to_int(_value(match, "DeductionStatus", "Status", "deduction_status")) or deduction_status
    if provider_id is not None:
        state.deduction_id = provider_id
    state.cdas_status = provider_status
    lifecycle = _lifecycle_from_code(provider_status)
    if lifecycle is None:
        raise CdasLifecycleError(502, "CDAS returned an unknown deduction status during reconciliation")
    state.lifecycle_status = lifecycle
    state.requires_reconciliation = False
    state.last_error = None
    state.last_provider_response = match
    state.last_synced_at = now
    _set_lifecycle_timestamp(state, lifecycle, now)
    mandate.status = lifecycle
    if lifecycle == "active" and mandate.activated_at is None:
        mandate.activated_at = now
    if lifecycle in {"settled", "deleted", "expired_or_auto_settled", "cancelled_or_rejected"}:
        mandate.completed_at = mandate.completed_at or now

    _record_event(
        db,
        state=state,
        actor_user_id=actor_user_id,
        event_type="reconciliation",
        request_type=None,
        request_snapshot={"EmployeeNo": mandate.employee_number, "DeductionStatus": deduction_status},
        response_snapshot=match,
        provider_status_code=200,
        success=True,
    )
    db.commit()
    db.refresh(state)
    db.refresh(mandate)
    return serialize_official_mandate(state, mandate)
