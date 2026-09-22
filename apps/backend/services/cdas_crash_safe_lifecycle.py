from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from integrations.cdas import CdasClient
from services.cdas_deduction_lifecycle import (
    CdasLifecycleError,
    get_official_mandate,
    modify_linked_active_deduction as _modify_linked_active_deduction,
    perform_linked_action as _perform_linked_action,
    settle_linked_deduction as _settle_linked_deduction,
)


def _arm_provider_write(
    db: Session,
    *,
    company_id: UUID,
    state_id: UUID,
    request_type: int,
    description: str,
):
    state, _ = get_official_mandate(db, company_id=company_id, state_id=state_id)
    if state.requires_reconciliation:
        raise CdasLifecycleError(409, "Reconcile this CDAS mandate before sending another state-changing request")

    previous_error = state.last_error
    state.last_request_type = request_type
    state.requires_reconciliation = True
    state.last_error = f"{description} submitted to CDAS; provider result has not yet been confirmed"
    db.commit()

    # The committed database value remains True during the outbound request. The
    # existing lifecycle implementation must see False locally so it can run its
    # normal validation and response handling. no_autoflush prevents this local
    # value from reaching PostgreSQL until the existing service commits a known
    # result. If the worker dies first, PostgreSQL safely remains armed.
    state.requires_reconciliation = False
    state.last_error = previous_error
    return state


def _restore_if_no_provider_result(db: Session, state) -> None:
    # A normal local validation failure happens before the provider call and
    # therefore must not leave the mandate blocked. If the underlying service
    # already persisted an ambiguous/incomplete provider result it will have set
    # requires_reconciliation=True again; preserve that state.
    if not state.requires_reconciliation:
        state.last_error = None
        db.commit()


async def perform_linked_action(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    actor_user_id: UUID,
    state_id: UUID,
    request_type: int,
):
    state = _arm_provider_write(
        db,
        company_id=company_id,
        state_id=state_id,
        request_type=request_type,
        description="CDAS lifecycle action",
    )
    try:
        with db.no_autoflush:
            return await _perform_linked_action(
                db,
                client=client,
                company_id=company_id,
                actor_user_id=actor_user_id,
                state_id=state_id,
                request_type=request_type,
            )
    except CdasLifecycleError:
        _restore_if_no_provider_result(db, state)
        raise


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
):
    state = _arm_provider_write(
        db,
        company_id=company_id,
        state_id=state_id,
        request_type=10,
        description="Active-deduction change",
    )
    try:
        with db.no_autoflush:
            return await _modify_linked_active_deduction(
                db,
                client=client,
                company_id=company_id,
                actor_user_id=actor_user_id,
                state_id=state_id,
                effective_date=effective_date,
                deduction_amount=deduction_amount,
                principal_amount=principal_amount,
                total_installment=total_installment,
            )
    except CdasLifecycleError:
        _restore_if_no_provider_result(db, state)
        raise


async def settle_linked_deduction(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    actor_user_id: UUID,
    state_id: UUID,
    effective_date: str,
    settlement_reason: int,
):
    state = _arm_provider_write(
        db,
        company_id=company_id,
        state_id=state_id,
        request_type=7,
        description="Settlement",
    )
    try:
        with db.no_autoflush:
            return await _settle_linked_deduction(
                db,
                client=client,
                company_id=company_id,
                actor_user_id=actor_user_id,
                state_id=state_id,
                effective_date=effective_date,
                settlement_reason=settlement_reason,
            )
    except CdasLifecycleError:
        _restore_if_no_provider_result(db, state)
        raise
