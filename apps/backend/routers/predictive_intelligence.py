from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.access_control import COMPANY_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.branch import CompanyBranch
from database.models.enums import UserRole
from database.models.predictive_intelligence import (
    PredictiveCashflowForecast,
    PredictiveIntelligenceRun,
    PredictiveLoanSignal,
)
from database.session import get_db
from services.predictive_intelligence_service import (
    cashflow_payload,
    generate_predictive_run,
    run_payload,
    signal_payload,
)


router = APIRouter(prefix="/predictive-intelligence", tags=["Predictive Intelligence"])
PREDICTIVE_RUN_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.CREDIT_ANALYST,
    UserRole.COLLECTIONS_OFFICER,
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


def _latest_run(db: Session, company_id: UUID, branch_id: UUID | None) -> PredictiveIntelligenceRun | None:
    scope_key = str(branch_id) if branch_id else "ALL"
    return db.query(PredictiveIntelligenceRun).filter(
        PredictiveIntelligenceRun.company_id == company_id,
        PredictiveIntelligenceRun.branch_scope_key == scope_key,
    ).order_by(PredictiveIntelligenceRun.generated_at.desc()).first()


@router.get("/overview")
def predictive_overview(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    branch = _resolve_branch(db, context, branch_id)
    run = _latest_run(db, context.company_id, branch)
    if not run:
        return {
            "latest_run": None,
            "signals": [],
            "cashflow": [],
            "high_risk_exposure": 0.0,
            "guardrails": {
                "advisory_only": True,
                "calibrated_probability_model": False,
                "automatic_credit_decisions": False,
                "automatic_collection_actions": False,
            },
        }
    signals = db.query(PredictiveLoanSignal).filter(
        PredictiveLoanSignal.run_id == run.id,
    ).order_by(PredictiveLoanSignal.risk_score.desc(), PredictiveLoanSignal.outstanding_balance.desc()).all()
    cashflow = db.query(PredictiveCashflowForecast).filter(
        PredictiveCashflowForecast.run_id == run.id,
    ).order_by(PredictiveCashflowForecast.horizon_days.asc()).all()
    high_risk_exposure = sum(
        float(row.outstanding_balance or 0)
        for row in signals
        if row.risk_band in {"high", "critical"}
    )
    return {
        "latest_run": run_payload(run),
        "signals": [signal_payload(row) for row in signals[:100]],
        "cashflow": [cashflow_payload(row) for row in cashflow],
        "high_risk_exposure": high_risk_exposure,
        "guardrails": {
            "advisory_only": True,
            "calibrated_probability_model": False,
            "automatic_credit_decisions": False,
            "automatic_collection_actions": False,
        },
    }


@router.post("/runs")
def create_predictive_run(
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    require_tenant_roles(context, PREDICTIVE_RUN_ROLES)
    branch = _resolve_branch(db, context, branch_id)
    run = generate_predictive_run(
        db,
        company_id=context.company_id,
        branch_id=branch,
        as_of=date.today(),
        run_type="on_demand",
        triggered_by_user_id=context.user.id,
    )
    return run_payload(run)


@router.get("/runs")
def list_predictive_runs(
    branch_id: UUID | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=365),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    branch = _resolve_branch(db, context, branch_id)
    scope_key = str(branch) if branch else "ALL"
    rows = db.query(PredictiveIntelligenceRun).filter(
        PredictiveIntelligenceRun.company_id == context.company_id,
        PredictiveIntelligenceRun.branch_scope_key == scope_key,
    ).order_by(PredictiveIntelligenceRun.generated_at.desc()).limit(limit).all()
    return [run_payload(row) for row in rows]


@router.get("/signals")
def list_predictive_signals(
    run_id: UUID | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    risk_band: str | None = Query(default=None),
    projected_par30_entry: bool | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    branch = _resolve_branch(db, context, branch_id)
    run = None
    if run_id:
        scope_key = str(branch) if branch else "ALL"
        run = db.query(PredictiveIntelligenceRun).filter(
            PredictiveIntelligenceRun.id == run_id,
            PredictiveIntelligenceRun.company_id == context.company_id,
            PredictiveIntelligenceRun.branch_scope_key == scope_key,
        ).first()
    else:
        run = _latest_run(db, context.company_id, branch)
    if not run:
        return []
    query = db.query(PredictiveLoanSignal).filter(PredictiveLoanSignal.run_id == run.id)
    if risk_band:
        query = query.filter(PredictiveLoanSignal.risk_band == risk_band)
    if projected_par30_entry is not None:
        query = query.filter(PredictiveLoanSignal.projected_par30_entry.is_(projected_par30_entry))
    rows = query.order_by(PredictiveLoanSignal.risk_score.desc(), PredictiveLoanSignal.outstanding_balance.desc()).limit(limit).all()
    return [signal_payload(row) for row in rows]
