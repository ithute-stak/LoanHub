from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.branch import CompanyBranch
from database.models.enums import OpeningSourceType, PaymentMethod, UserRole
from database.session import get_db
from services.backdated_opening_adjustment_service import create_backdated_opening_adjustment


router = APIRouter(prefix="/expense-management", tags=["Expense and Money Management"])

HISTORICAL_CORRECTION_ROLES = COMPANY_MANAGEMENT_ROLES | {UserRole.FINANCE_OFFICER}


class BackdatedOpeningAdjustmentCreate(BaseModel):
    branch_id: UUID | None = None
    business_date: date
    source_type: OpeningSourceType = OpeningSourceType.OPENING_ADJUSTMENT
    payment_method: PaymentMethod = PaymentMethod.CASH
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    currency: str = Field(default="LSL", min_length=3, max_length=3)
    description: str = Field(min_length=3, max_length=500)
    correction_reason: str = Field(min_length=10, max_length=1000)
    source_reference: str | None = Field(default=None, max_length=180)
    proof_reference: str | None = Field(default=None, max_length=180)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str | None = Field(default=None, max_length=2000)
    corrected_declared_closing_balance: Decimal | None = Field(
        default=None,
        max_digits=15,
        decimal_places=2,
    )


class BackdatedOpeningAdjustmentRead(BaseModel):
    source_id: UUID
    ledger_id: UUID
    business_date: date
    source_reference: str
    old_opening_balance: Decimal
    new_opening_balance: Decimal
    old_expected_closing_balance: Decimal
    new_expected_closing_balance: Decimal
    target_submission_sequence: int | None = None
    downstream_days_refreshed: int
    downstream_days_revised: int
    current_opening_balance: Decimal | None = None
    current_expected_closing_balance: Decimal | None = None


def _company_id(context: TenantContext) -> UUID:
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company is required")
    return context.company_id


def _resolve_branch(db: Session, context: TenantContext, requested: UUID | None) -> UUID:
    company_id = _company_id(context)
    branch_id = requested or context.branch_id
    if branch_id is None:
        from services.treasury_service import get_or_create_settings

        branch_id = get_or_create_settings(db, company_id).headquarters_branch_id
    if branch_id is None:
        raise HTTPException(status_code=409, detail="Select a branch before recording a historical opening correction")
    branch = db.get(CompanyBranch, branch_id)
    if not branch or branch.company_id != company_id:
        raise HTTPException(status_code=404, detail="Branch was not found in the active company")
    assert_branch_scope(context, branch_id)
    return branch_id


@router.post(
    "/opening-sources/backdated-adjustment",
    response_model=BackdatedOpeningAdjustmentRead,
)
def add_backdated_opening_adjustment(
    payload: BackdatedOpeningAdjustmentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HISTORICAL_CORRECTION_ROLES)
    branch_id = _resolve_branch(db, context, payload.branch_id)

    try:
        result = create_backdated_opening_adjustment(
            db,
            company_id=_company_id(context),
            branch_id=branch_id,
            user_id=context.user.id,
            business_date=payload.business_date,
            source_type=payload.source_type,
            payment_method=payload.payment_method,
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            correction_reason=payload.correction_reason,
            source_reference=payload.source_reference,
            proof_reference=payload.proof_reference,
            proof_url=payload.proof_url,
            proof_notes=payload.proof_notes,
            corrected_declared_closing_balance=payload.corrected_declared_closing_balance,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return BackdatedOpeningAdjustmentRead(
        source_id=result.source.id,
        ledger_id=result.target_ledger.id,
        business_date=result.target_ledger.business_date,
        source_reference=result.source.source_reference,
        old_opening_balance=result.old_opening_balance,
        new_opening_balance=result.new_opening_balance,
        old_expected_closing_balance=result.old_expected_closing_balance,
        new_expected_closing_balance=result.new_expected_closing_balance,
        target_submission_sequence=result.target_submission_sequence,
        downstream_days_refreshed=result.downstream_days_refreshed,
        downstream_days_revised=result.downstream_days_revised,
        current_opening_balance=result.current_opening_balance,
        current_expected_closing_balance=result.current_expected_closing_balance,
    )
