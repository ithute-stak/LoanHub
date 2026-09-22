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
    register_loan_deduction,
    serialize_official_mandate,
    settle_linked_deduction,
)


router = APIRouter(prefix="/cdas", tags=["CDAS Official Loan Lifecycle"])

CDAS_LIFECYCLE_ROLES = set(LENDING_ROLES)
CDAS_RECONCILIATION_ROLES = set(LENDING_ROLES) | set(FINANCE_ROLES) | set(COLLECTIONS_ROLES)
CDAS_SETTLEMENT_ROLES = set(LENDING_ROLES) | set(FINANCE_ROLES) | set(COLLECTIONS_ROLES)


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


@router.post("/loan-deductions")
async def register_cdas_loan_deduction(
    payload: CdasLoanDeductionRegistrationRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Register a CDAS deduction that is permanently tied to a LoanHub loan.

    A local mandate is committed before the provider write. If CDAS returns an
    uncertain authentication/server/network failure, LoanHub preserves the link
    and requires explicit reconciliation instead of replaying the write.
    """
    company_id = _require_company(context)
    require_tenant_roles(context, CDAS_LIFECYCLE_ROLES)
    try:
        client = get_company_cdas_client(db, company_id)
        return await register_loan_deduction(
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
