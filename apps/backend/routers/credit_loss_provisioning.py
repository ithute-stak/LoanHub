from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import COMPANY_ROLES, FINANCE_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.credit_loss_provisioning import CreditLossProvisionPolicy, CreditLossProvisionRun
from database.models.enums import UserRole
from database.session import get_db
from services.credit_loss_accounting_bootstrap import ensure_credit_loss_accounts
from services.credit_loss_provisioning_service import approve_and_post, generate_run, get_or_create_policy, run_payload


router = APIRouter(prefix="/credit-loss-provisioning", tags=["Credit Loss Provisioning"])
RUN_ROLES = FINANCE_ROLES | {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN, UserRole.RISK_MANAGER, UserRole.CREDIT_ANALYST, UserRole.BRANCH_MANAGER}
APPROVAL_ROLES = {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN, UserRole.FINANCE_MANAGER, UserRole.RISK_MANAGER}


class GenerateProvisionRequest(BaseModel):
    as_of_date: date
    management_overlay: Decimal = Field(default=Decimal("0"))
    overlay_reason: str | None = Field(default=None, max_length=4000)


class ProvisionPolicyUpdate(BaseModel):
    rates: dict[str, str | int | float]
    description: str | None = Field(default=None, max_length=4000)


def _scope(context: TenantContext) -> None:
    require_tenant_roles(context, COMPANY_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=403, detail="A company-scoped role is required")


@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    query = db.query(CreditLossProvisionRun).filter(CreditLossProvisionRun.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(CreditLossProvisionRun.branch_id == context.branch_id)
    latest = query.order_by(CreditLossProvisionRun.as_of_date.desc()).first()
    recent = query.order_by(CreditLossProvisionRun.as_of_date.desc()).limit(24).all()
    return {
        "latest": run_payload(db, latest) if latest else None,
        "history": [run_payload(db, row) for row in recent],
        "guardrails": {
            "maker_checker_required": True,
            "approval_posts_accounting_journal": True,
            "formal_accounting_policy_review_required": True,
        },
    }


@router.post("/runs")
def create_run(
    payload: GenerateProvisionRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    require_tenant_roles(context, RUN_ROLES)
    if payload.as_of_date > date.today():
        raise HTTPException(status_code=422, detail="Provision runs cannot be future-dated")
    run = generate_run(
        db,
        context,
        as_of_date=payload.as_of_date,
        management_overlay=payload.management_overlay,
        overlay_reason=payload.overlay_reason,
    )
    return run_payload(db, run, include_lines=True)


@router.get("/runs")
def list_runs(
    limit: int = Query(default=50, ge=1, le=250),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    query = db.query(CreditLossProvisionRun).filter(CreditLossProvisionRun.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(CreditLossProvisionRun.branch_id == context.branch_id)
    return [run_payload(db, row) for row in query.order_by(CreditLossProvisionRun.as_of_date.desc()).limit(limit).all()]


@router.get("/runs/{run_id}")
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    row = db.query(CreditLossProvisionRun).filter(
        CreditLossProvisionRun.id == run_id,
        CreditLossProvisionRun.company_id == context.company_id,
    ).first()
    if not row or (context.branch_id and row.branch_id != context.branch_id):
        raise HTTPException(status_code=404, detail="Credit-loss provision run not found")
    return run_payload(db, row, include_lines=True)


@router.post("/runs/{run_id}/approve")
def approve_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    require_tenant_roles(context, APPROVAL_ROLES)
    ensure_credit_loss_accounts(db, context.company_id)
    return run_payload(db, approve_and_post(db, context, run_id), include_lines=True)


@router.get("/policy")
def get_policy(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    policy = get_or_create_policy(db, context)
    db.commit()
    return {
        "id": str(policy.id), "name": policy.name, "version": policy.version,
        "status": policy.status, "rates": policy.rates or {}, "description": policy.description,
    }


@router.put("/policy")
def update_policy(
    payload: ProvisionPolicyUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    require_tenant_roles(context, APPROVAL_ROLES)
    current = get_or_create_policy(db, context)
    current.status = "superseded"
    next_policy = CreditLossProvisionPolicy(
        company_id=context.company_id,
        name=current.name,
        version=current.version + 1,
        status="active",
        rates=payload.rates,
        description=payload.description or current.description,
        configured_by_user_id=context.user.id,
    )
    db.add(next_policy)
    db.commit()
    db.refresh(next_policy)
    return {"id": str(next_policy.id), "name": next_policy.name, "version": next_policy.version, "status": next_policy.status, "rates": next_policy.rates, "description": next_policy.description}
