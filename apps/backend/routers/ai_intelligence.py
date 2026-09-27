from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.access_control import COMPANY_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.ai_intelligence import AIIntelligenceInsight, AIIntelligenceRun
from database.models.enums import UserRole
from database.session import get_db
from services.ai_intelligence_service import (
    generate_intelligence_run,
    insight_payload,
    review_insight,
    run_payload,
)


router = APIRouter(prefix="/ai-intelligence", tags=["AI Intelligence"])
AI_RUN_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.CREDIT_ANALYST,
    UserRole.COLLECTIONS_OFFICER,
}
AI_REVIEW_ROLES = AI_RUN_ROLES | {UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR}


class InsightReviewRequest(BaseModel):
    status: str = Field(pattern="^(reviewed|dismissed|actioned)$")
    feedback: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=4000)


def _scope(context: TenantContext) -> None:
    require_tenant_roles(context, COMPANY_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=403, detail="A company-scoped role is required")


@router.get("/overview")
def ai_intelligence_overview(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    query = db.query(AIIntelligenceRun).filter(AIIntelligenceRun.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(AIIntelligenceRun.branch_id == context.branch_id)
    latest = query.order_by(AIIntelligenceRun.created_at.desc()).first()

    insights = db.query(AIIntelligenceInsight).filter(AIIntelligenceInsight.company_id == context.company_id)
    if context.branch_id:
        insights = insights.filter(AIIntelligenceInsight.branch_id.in_([None, context.branch_id]))
    open_rows = insights.filter(AIIntelligenceInsight.status == "open").order_by(
        AIIntelligenceInsight.created_at.desc()
    ).limit(100).all()
    domain_counts = {
        domain: count
        for domain, count in insights.filter(AIIntelligenceInsight.status == "open").with_entities(
            AIIntelligenceInsight.domain,
            func.count(AIIntelligenceInsight.id),
        ).group_by(AIIntelligenceInsight.domain).all()
    }
    return {
        "latest_run": run_payload(latest) if latest else None,
        "open_count": len(open_rows),
        "critical_count": sum(row.severity == "critical" for row in open_rows),
        "high_count": sum(row.severity == "high" for row in open_rows),
        "domain_counts": domain_counts,
        "top_insights": [insight_payload(row) for row in open_rows[:20]],
        "guardrails": {
            "advisory_only": True,
            "automatic_credit_decisions": False,
            "automatic_disbursement": False,
            "human_review_required": True,
        },
    }


@router.post("/runs")
def run_ai_intelligence(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    require_tenant_roles(context, AI_RUN_ROLES)
    return run_payload(generate_intelligence_run(db, context))


@router.get("/runs")
def list_ai_intelligence_runs(
    limit: int = Query(default=50, ge=1, le=250),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    query = db.query(AIIntelligenceRun).filter(AIIntelligenceRun.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(AIIntelligenceRun.branch_id == context.branch_id)
    return [run_payload(row) for row in query.order_by(AIIntelligenceRun.created_at.desc()).limit(limit).all()]


@router.get("/insights")
def list_ai_intelligence_insights(
    status: str | None = None,
    severity: str | None = None,
    domain: str | None = None,
    limit: int = Query(default=250, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    query = db.query(AIIntelligenceInsight).filter(AIIntelligenceInsight.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(AIIntelligenceInsight.branch_id.in_([None, context.branch_id]))
    if status:
        query = query.filter(AIIntelligenceInsight.status == status)
    if severity:
        query = query.filter(AIIntelligenceInsight.severity == severity)
    if domain:
        query = query.filter(AIIntelligenceInsight.domain == domain)
    rows = query.order_by(AIIntelligenceInsight.created_at.desc()).limit(limit).all()
    return [insight_payload(row) for row in rows]


@router.patch("/insights/{insight_id}")
def review_ai_intelligence_insight(
    insight_id: UUID,
    payload: InsightReviewRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    require_tenant_roles(context, AI_REVIEW_ROLES)
    row = review_insight(
        db,
        context,
        insight_id,
        status=payload.status,
        feedback=payload.feedback,
        note=payload.note,
    )
    return insight_payload(row)
