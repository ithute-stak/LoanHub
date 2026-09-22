from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COLLECTIONS_ROLES,
    FINANCE_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.cdas_official import CdasOfficialMandateEvent
from database.session import get_db
from integrations.cdas import CdasError
from services.cdas_config_service import get_company_cdas_client
from services.cdas_deduction_lifecycle import (
    CdasLifecycleError,
    get_official_mandate,
    get_official_mandate_for_loan,
    modify_linked_active_deduction,
    perform_linked_action,
    reconcile_linked_deduction,
    serialize_official_mandate,
    settle_linked_deduction,
)
from services.cdas_registration_retry import retry_failed_registration
from services.cdas_registration_workflow import register_loan_deduction_safely


router = APIRouter(prefix="/cdas", tags=["CDAS Official Loan Lifecycle"])

CDAS_LIFECYCLE_ROLES = set(LENDING_ROLES)
CDAS_RECONCILIATION_ROLES = set(LENDING_ROLES) | set(FINANCE_ROLES) | set(COLLECTIONS_ROLES)
CDAS_SETTLEMENT_ROLES = set(LENDING_ROLES) | set(FINANCE_ROLES) | set(COLLECTIONS_ROLES)

# Keep the provider workflow enforceable on the backend. The UI also hides
# invalid actions, but direct API callers must not be able to skip lifecycle
# stages or use the generic endpoint to mutate an already-active deduction.
CDAS_ACTION_ALLOWED_FROM: dict[int, set[str]] = {
    3: {"registered", "reserved"},
    4: {"reviewed"},
    5: {"approved"},
    6: {"registered", "reserved", "reviewed", "approved"},
    9: {"registered", "reserved", "reviewed", "approved", "cancelled_or_rejected"},
    10: {"registered", "reserved", "reviewed", "approved"},
}
ACTIVE_LIFECYCLE_STATUSES = {"active", "changed"}


class CdasLoanDeductionRegistrationRequest(BaseModel):
    loan_id: UUID
    employee_no: str = Field(min_length=1, max_length=100)
    item_code: str = Field(min_length=1, max_length=100)
    reference_no: str = Field(min_length=1, max_length=200)
    loan_policy: int = Field(default=0, ge=0)
    deduction_amount: Decimal = Field(gt=0)
    principal_amount: Decimal = Field(gt=0)
    total_installment: int = Field(gt=0, le=600)
    effective_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    borrower_consent: bool


class CdasRegistrationRetryRequest(BaseModel):
    item_code: str = Field(min_length=1, max_length=100)
    reference_no: str = Field(min_length=1, max_length=200)
    loan_policy: int = Field(default=0, ge=0)
    deduction_amount: Decimal = Field(gt=0)
    principal_amount: Decimal = Field(gt=0)
    total_installment: int = Field(gt=0, le=600)
    effective_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class CdasLinkedActionRequest(BaseModel):
    request_type: Literal[3, 4, 5, 6, 9, 10]


class CdasLinkedModifyRequest(BaseModel):
    effective_date: str = Field(min_length=7, max_length=40)
    deduction_amount: Decimal | None = Field(default=None, gt=0)
    principal_amount: Decimal | None = Field(default=None, gt=0)
    total_installment: int | None = Field(default=None, gt=0, le=600)


class CdasLinkedSettlementRequest(BaseModel):
    effective_date: str = Field(min_length=7, max_length=40)
    settlement_reason: int = Field(ge=1, le=4)


def _require_company(context: TenantContext) -> UUID:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    return context.company_id


def _lifecycle_http_error(exc: CdasLifecycleError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _cdas_http_error(exc: CdasError) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code <= 599 else 502
    return HTTPException(
        status_code=status,
        detail={"provider": "CDAS", "code": exc.status_code, "message": exc.message},
    )


def _require_lifecycle_transition(lifecycle_status: str | None, request_type: int) -> None:
    current = str(lifecycle_status or "").strip().lower()
    allowed = CDAS_ACTION_ALLOWED_FROM.get(request_type, set())
    if current not in allowed:
        raise CdasLifecycleError(
            409,
            f"CDAS request type {request_type} is not allowed while this mandate is {current or 'unknown'}",
        )


def _require_active_lifecycle(lifecycle_status: str | None, operation: str) -> None:
    current = str(lifecycle_status or "").strip().lower()
    if current not in ACTIVE_LIFECYCLE_STATUSES:
        raise CdasLifecycleError(
            409,
            f"Only an active CDAS deduction can be {operation}; current lifecycle is {current or 'unknown'}",
        )


def _serialize_event(event: CdasOfficialMandateEvent) -> dict[str, object]:
    return {
        "id": str(event.id),
        "state_id": str(event.state_id),
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "event_type": event.event_type,
        "request_type": event.request_type,
        "request_snapshot": event.request_snapshot or {},
        "response_snapshot": event.response_snapshot or {},
        "provider_status_code": event.provider_status_code,
        "success": bool(event.success),
        "message": event.message,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
    }


@router.post("/loan-deductions")
async def register_cdas_loan_deduction(
    payload: CdasLoanDeductionRegistrationRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Register a CDAS deduction that is permanently tied to a LoanHub loan.

    LoanHub persists an uncertain-before-write marker before CDAS receives the
    mutation. A process crash or uncertain provider failure therefore requires
    explicit reconciliation instead of making the registration replayable.
    """
    company_id = _require_company(context)
    require_tenant_roles(context, CDAS_LIFECYCLE_ROLES)
    try:
        client = get_company_cdas_client(db, company_id)
        return await register_loan_deduction_safely(
            db,
            client=client,
            company_id=company_id,
            branch_id=context.branch_id,
            actor_user_id=context.user.id,
            loan_id=payload.loan_id,
            employee_no=payload.employee_no,
            item_code=payload.item_code,
            reference_no=payload.reference_no,
            loan_policy=payload.loan_policy,
            deduction_amount=payload.deduction_amount,
            principal_amount=payload.principal_amount,
            total_installment=payload.total_installment,
            effective_month=payload.effective_month,
            borrower_consent=payload.borrower_consent,
        )
    except CdasLifecycleError as exc:
        raise _lifecycle_http_error(exc) from exc
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/loan-deductions/{state_id}/retry-registration")
async def retry_cdas_loan_deduction_registration(
    state_id: UUID,
    payload: CdasRegistrationRetryRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Correct and retry only a previously confirmed, retry-safe CDAS rejection."""
    company_id = _require_company(context)
    require_tenant_roles(context, CDAS_LIFECYCLE_ROLES)
    try:
        client = get_company_cdas_client(db, company_id)
        return await retry_failed_registration(
            db,
            client=client,
            company_id=company_id,
            actor_user_id=context.user.id,
            state_id=state_id,
            item_code=payload.item_code,
            reference_no=payload.reference_no,
            loan_policy=payload.loan_policy,
            deduction_amount=payload.deduction_amount,
            principal_amount=payload.principal_amount,
            total_installment=payload.total_installment,
            effective_month=payload.effective_month,
        )
    except CdasLifecycleError as exc:
        raise _lifecycle_http_error(exc) from exc
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.get("/loans/{loan_id}/deduction")
def get_cdas_deduction_for_loan(
    loan_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    company_id = _require_company(context)
    row = get_official_mandate_for_loan(db, company_id=company_id, loan_id=loan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="This loan does not have an official CDAS mandate")
    state, mandate = row
    return serialize_official_mandate(state, mandate)


@router.get("/loan-deductions/{state_id}")
def get_cdas_loan_deduction(
    state_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    company_id = _require_company(context)
    try:
        state, mandate = get_official_mandate(db, company_id=company_id, state_id=state_id)
    except CdasLifecycleError as exc:
        raise _lifecycle_http_error(exc) from exc
    return serialize_official_mandate(state, mandate)


@router.get("/loan-deductions/{state_id}/events")
def get_cdas_loan_deduction_events(
    state_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return the append-only company-scoped audit trail for a linked mandate."""
    company_id = _require_company(context)
    try:
        get_official_mandate(db, company_id=company_id, state_id=state_id)
    except CdasLifecycleError as exc:
        raise _lifecycle_http_error(exc) from exc

    events = (
        db.query(CdasOfficialMandateEvent)
        .filter(
            CdasOfficialMandateEvent.company_id == company_id,
            CdasOfficialMandateEvent.state_id == state_id,
        )
        .order_by(CdasOfficialMandateEvent.occurred_at.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_event(event) for event in events]


@router.post("/loan-deductions/{state_id}/actions")
async def run_linked_cdas_action(
    state_id: UUID,
    payload: CdasLinkedActionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Review/approve/activate/cancel/delete/update a linked CDAS mandate."""
    company_id = _require_company(context)
    require_tenant_roles(context, CDAS_LIFECYCLE_ROLES)
    try:
        state, _ = get_official_mandate(db, company_id=company_id, state_id=state_id)
        _require_lifecycle_transition(state.lifecycle_status, payload.request_type)
        client = get_company_cdas_client(db, company_id)
        return await perform_linked_action(
            db,
            client=client,
            company_id=company_id,
            actor_user_id=context.user.id,
            state_id=state_id,
            request_type=payload.request_type,
        )
    except CdasLifecycleError as exc:
        raise _lifecycle_http_error(exc) from exc
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/loan-deductions/{state_id}/modify-active")
async def modify_linked_cdas_deduction(
    state_id: UUID,
    payload: CdasLinkedModifyRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    company_id = _require_company(context)
    require_tenant_roles(context, CDAS_LIFECYCLE_ROLES)
    try:
        state, _ = get_official_mandate(db, company_id=company_id, state_id=state_id)
        _require_active_lifecycle(state.lifecycle_status, "modified")
        client = get_company_cdas_client(db, company_id)
        return await modify_linked_active_deduction(
            db,
            client=client,
            company_id=company_id,
            actor_user_id=context.user.id,
            state_id=state_id,
            effective_date=payload.effective_date,
            deduction_amount=payload.deduction_amount,
            principal_amount=payload.principal_amount,
            total_installment=payload.total_installment,
        )
    except CdasLifecycleError as exc:
        raise _lifecycle_http_error(exc) from exc
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/loan-deductions/{state_id}/settle")
async def settle_linked_cdas_loan_deduction(
    state_id: UUID,
    payload: CdasLinkedSettlementRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    company_id = _require_company(context)
    require_tenant_roles(context, CDAS_SETTLEMENT_ROLES)
    try:
        state, _ = get_official_mandate(db, company_id=company_id, state_id=state_id)
        _require_active_lifecycle(state.lifecycle_status, "settled")
        client = get_company_cdas_client(db, company_id)
        return await settle_linked_deduction(
            db,
            client=client,
            company_id=company_id,
            actor_user_id=context.user.id,
            state_id=state_id,
            effective_date=payload.effective_date,
            settlement_reason=payload.settlement_reason,
        )
    except CdasLifecycleError as exc:
        raise _lifecycle_http_error(exc) from exc
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc


@router.post("/loan-deductions/{state_id}/reconcile")
async def reconcile_linked_cdas_loan_deduction(
    state_id: UUID,
    deduction_status: int = Query(ge=1, le=10),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Explicitly reconcile a mandate after an uncertain write or status change.

    This is intentionally user-triggered because CDAS documents a finite daily
    request allowance. It never runs as a page-load/background request.
    """
    company_id = _require_company(context)
    require_tenant_roles(context, CDAS_RECONCILIATION_ROLES)
    try:
        client = get_company_cdas_client(db, company_id)
        return await reconcile_linked_deduction(
            db,
            client=client,
            company_id=company_id,
            actor_user_id=context.user.id,
            state_id=state_id,
            deduction_status=deduction_status,
        )
    except CdasLifecycleError as exc:
        raise _lifecycle_http_error(exc) from exc
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
