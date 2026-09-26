from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_user_context,
    require_tenant_roles,
)
from database.models.credit_committee import CreditCommitteeCase
from database.models.enums import UserRole
from database.session import get_db
from services.credit_committee_report_service import build_credit_committee_pdf
from services.credit_committee_service import (
    application_or_404,
    assessment_payload,
    case_or_404,
    case_payload,
    cast_vote,
    condition_payload,
    configure_case_governance,
    dashboard_payload,
    ensure_case,
    finalize_case,
    submit_assessment,
    update_condition,
)


router = APIRouter(prefix="/credit-committee", tags=["Credit Committee & Underwriting"])

VIEW_ROLES = COMPANY_MANAGEMENT_ROLES | LENDING_ROLES | {
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
}
ANALYST_ROLES = COMPANY_MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.CREDIT_ANALYST,
    UserRole.RISK_MANAGER,
}
COMMITTEE_VOTE_ROLES = COMPANY_MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.RISK_MANAGER,
}
FINALIZE_ROLES = COMMITTEE_VOTE_ROLES
CONDITION_UPDATE_ROLES = ANALYST_ROLES | COMMITTEE_VOTE_ROLES


class ConditionProposal(BaseModel):
    title: str = Field(min_length=2, max_length=220)
    description: str | None = Field(default=None, max_length=4000)
    condition_type: Literal["pre_contract", "pre_disbursement", "monitoring"] = "pre_disbursement"
    due_date: date | None = None


class UnderwritingAssessmentCreate(BaseModel):
    proposed_amount: Decimal | None = Field(default=None, gt=0)
    proposed_installment: Decimal | None = Field(default=None, ge=0)
    proposed_term: int | None = Field(default=None, ge=1, le=600)
    verified_income: Decimal | None = Field(default=None, ge=0)
    household_expenses: Decimal | None = Field(default=None, ge=0)
    existing_debt_installments: Decimal | None = Field(default=None, ge=0)
    dti_percent: Decimal | None = Field(default=None, ge=0)
    affordability_headroom: Decimal | None = None
    bureau_score: int | None = None
    bureau_risk_grade: str | None = Field(default=None, max_length=40)
    risk_score: Decimal | None = Field(default=None, ge=0, le=100)
    risk_grade: Literal["low", "medium", "high", "critical"]
    recommendation: Literal["approve", "approve_with_conditions", "reject", "refer"]
    rationale: str = Field(min_length=10, max_length=12000)
    strengths: list[str] = Field(default_factory=list, max_length=50)
    weaknesses: list[str] = Field(default_factory=list, max_length=50)
    exceptions: list[str] = Field(default_factory=list, max_length=50)
    mitigants: list[str] = Field(default_factory=list, max_length=50)
    proposed_conditions: list[ConditionProposal] = Field(default_factory=list, max_length=30)


class CommitteeVoteCreate(BaseModel):
    decision: Literal["approve", "approve_with_conditions", "reject", "abstain"]
    rationale: str = Field(default="", max_length=8000)
    conditions: list[ConditionProposal] = Field(default_factory=list, max_length=30)


class CommitteeFinalizeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=8000)
    decision: Literal["approved", "conditionally_approved", "rejected"] | None = None
    override_reason: str | None = Field(default=None, max_length=8000)


class CommitteeGovernanceUpdate(BaseModel):
    required_votes: int = Field(ge=1, le=20)
    approval_threshold_percent: Decimal = Field(gt=0, le=100)
    maker_checker_required: bool = True
    reason: str = Field(default="", max_length=4000)


class ConditionUpdate(BaseModel):
    status: Literal["open", "satisfied", "waived", "failed"]
    evidence_note: str | None = Field(default=None, max_length=8000)
    waiver_reason: str | None = Field(default=None, max_length=8000)


def _case_query(db: Session, context: TenantContext):
    query = db.query(CreditCommitteeCase).filter(CreditCommitteeCase.company_id == context.company_id)
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(CreditCommitteeCase.branch_id == context.branch_id)
    return query


@router.get("/dashboard")
def credit_committee_dashboard(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, VIEW_ROLES)
    return dashboard_payload(db, context)


@router.get("/cases")
def list_credit_committee_cases(
    status: str | None = None,
    limit: int = Query(default=250, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, VIEW_ROLES)
    query = _case_query(db, context)
    if status:
        query = query.filter(CreditCommitteeCase.status == status.strip().lower())
    rows = query.order_by(CreditCommitteeCase.created_at.desc()).limit(limit).all()
    return [case_payload(db, row) for row in rows]


@router.post("/intake/{application_id}", status_code=201)
def intake_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ANALYST_ROLES)
    application = application_or_404(db, context, application_id)
    if not application.credit_committee_required:
        raise HTTPException(status_code=409, detail="This historical application is not governed by the Credit Committee requirement")
    case = ensure_case(db, context, application, actor_user_id=context.user.id)
    return case_payload(db, case, include_events=True)


@router.get("/cases/{case_id}")
def credit_committee_case_detail(
    case_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, VIEW_ROLES)
    return case_payload(db, case_or_404(db, context, case_id), include_events=True)


@router.patch("/cases/{case_id}/governance")
def update_committee_governance(
    case_id: UUID,
    payload: CommitteeGovernanceUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    case = configure_case_governance(
        db,
        context,
        case_or_404(db, context, case_id, lock=True),
        required_votes=payload.required_votes,
        approval_threshold_percent=payload.approval_threshold_percent,
        maker_checker_required=payload.maker_checker_required,
        reason=payload.reason,
    )
    return case_payload(db, case, include_events=True)


@router.post("/cases/{case_id}/assessment", status_code=201)
def submit_underwriting_assessment(
    case_id: UUID,
    payload: UnderwritingAssessmentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, ANALYST_ROLES)
    row = submit_assessment(
        db,
        context,
        case_or_404(db, context, case_id, lock=True),
        proposed_amount=payload.proposed_amount,
        proposed_installment=payload.proposed_installment,
        proposed_term=payload.proposed_term,
        verified_income=payload.verified_income,
        household_expenses=payload.household_expenses,
        existing_debt_installments=payload.existing_debt_installments,
        dti_percent=payload.dti_percent,
        affordability_headroom=payload.affordability_headroom,
        bureau_score=payload.bureau_score,
        bureau_risk_grade=payload.bureau_risk_grade,
        risk_score=payload.risk_score,
        risk_grade=payload.risk_grade,
        recommendation=payload.recommendation,
        rationale=payload.rationale,
        strengths=payload.strengths,
        weaknesses=payload.weaknesses,
        exceptions=payload.exceptions,
        mitigants=payload.mitigants,
        proposed_conditions=[item.model_dump(mode="json") for item in payload.proposed_conditions],
    )
    return assessment_payload(row)


@router.put("/cases/{case_id}/vote")
def record_committee_vote(
    case_id: UUID,
    payload: CommitteeVoteCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, COMMITTEE_VOTE_ROLES)
    row = cast_vote(
        db,
        context,
        case_or_404(db, context, case_id, lock=True),
        decision=payload.decision,
        rationale=payload.rationale,
        conditions=[item.model_dump(mode="json") for item in payload.conditions],
    )
    case = case_or_404(db, context, case_id)
    return {"vote": {"id": str(row.id), "decision": row.decision}, "case": case_payload(db, case, include_events=True)}


@router.post("/cases/{case_id}/finalize")
def finalize_committee_case(
    case_id: UUID,
    payload: CommitteeFinalizeRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, FINALIZE_ROLES)
    case = finalize_case(
        db,
        context,
        case_or_404(db, context, case_id, lock=True),
        reason=payload.reason,
        requested_decision=payload.decision,
        override_reason=payload.override_reason,
        allow_override=context.role in COMPANY_MANAGEMENT_ROLES,
    )
    return case_payload(db, case, include_events=True)


@router.patch("/cases/{case_id}/conditions/{condition_id}")
def resolve_committee_condition(
    case_id: UUID,
    condition_id: UUID,
    payload: ConditionUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, CONDITION_UPDATE_ROLES)
    if payload.status == "waived" and context.role not in (COMPANY_MANAGEMENT_ROLES | {UserRole.RISK_MANAGER}):
        raise HTTPException(status_code=403, detail="Only company management or the risk manager may waive a credit condition")
    row = update_condition(
        db,
        context,
        case_or_404(db, context, case_id, lock=True),
        condition_id,
        status=payload.status,
        evidence_note=payload.evidence_note,
        waiver_reason=payload.waiver_reason,
    )
    case = case_or_404(db, context, case_id)
    return {"condition": condition_payload(row), "case": case_payload(db, case, include_events=True)}


@router.get("/cases/{case_id}/credit-memo.pdf")
def credit_committee_pdf(
    case_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_tenant_roles(context, VIEW_ROLES)
    case = case_or_404(db, context, case_id)
    content = build_credit_committee_pdf(db, case)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={case.case_reference}-credit-memo.pdf"},
    )
