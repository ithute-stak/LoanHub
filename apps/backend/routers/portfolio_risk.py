from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.access_control import COMPANY_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.branch import CompanyBranch
from database.models.enums import UserRole
from database.session import get_db
from services.portfolio_risk_service import (
    build_overview,
    generate_snapshot,
    overview_csv,
    risk_history,
)


router = APIRouter(prefix="/portfolio-risk", tags=["Portfolio Risk Intelligence"])
SNAPSHOT_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.CREDIT_ANALYST,
}


def _scope(context: TenantContext) -> None:
    require_tenant_roles(context, COMPANY_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=403, detail="A company-scoped role is required")


def _resolve_branch(db: Session, context: TenantContext, requested: UUID | None) -> UUID | None:
    if context.branch_id:
        if requested and requested != context.branch_id:
            raise HTTPException(status_code=403, detail="Branch-scoped users cannot inspect another branch")
        return context.branch_id
    if not requested:
        return None
    exists = db.query(CompanyBranch.id).filter(
        CompanyBranch.id == requested,
        CompanyBranch.company_id == context.company_id,
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Branch was not found in this company")
    return requested


@router.get("/overview")
def portfolio_risk_overview(
    as_of: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    target = as_of or date.today()
    if target > date.today():
        raise HTTPException(status_code=422, detail="Portfolio risk as_of cannot be in the future")
    if target != date.today():
        raise HTTPException(status_code=422, detail="Use risk history for prior dates; live overview is generated for today")
    branch = _resolve_branch(db, context, branch_id)
    return build_overview(db, company_id=context.company_id, branch_id=branch, as_of=target)


@router.post("/snapshot")
def create_portfolio_risk_snapshot(
    snapshot_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    require_tenant_roles(context, SNAPSHOT_ROLES)
    target = snapshot_date or date.today()
    if target > date.today():
        raise HTTPException(status_code=422, detail="Portfolio risk snapshots cannot be future-dated")
    if target != date.today():
        raise HTTPException(status_code=422, detail="Historical risk snapshots cannot be reconstructed from current loan state")
    run = generate_snapshot(
        db,
        company_id=context.company_id,
        snapshot_date=target,
        triggered_by_user_id=context.user.id,
    )
    return {
        "run_reference": run.run_reference,
        "snapshot_date": run.snapshot_date.isoformat(),
        "loan_count": run.loan_count,
        "active_exposure": float(run.active_exposure or 0),
        "par_30_amount": float(run.par_30_amount or 0),
        "summary": dict(run.summary or {}),
    }


@router.get("/history")
def portfolio_risk_history(
    branch_id: UUID | None = Query(default=None),
    limit: int = Query(default=120, ge=1, le=730),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    branch = _resolve_branch(db, context, branch_id)
    return risk_history(db, company_id=context.company_id, branch_id=branch, limit=limit)


@router.get("/export.csv")
def export_portfolio_risk_csv(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    branch = _resolve_branch(db, context, branch_id)
    overview = build_overview(db, company_id=context.company_id, branch_id=branch, as_of=date.today())
    return Response(
        content=overview_csv(overview),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=portfolio-risk-{date.today().isoformat()}.csv"},
    )
