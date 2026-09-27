from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, COMPANY_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.company_operations_phase2 import (
    CompanyBudgetLine,
    CompanyBudgetPlan,
    InternalAuditEngagement,
    InternalAuditFinding,
    ProcurementRequest,
    ProcurementVendor,
)
from database.session import get_db

router = APIRouter(prefix="/company-operations-phase2", tags=["Specialised Company Operations Phase 2"])


def _scope(context: TenantContext) -> None:
    require_tenant_roles(context, COMPANY_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=403, detail="A company-scoped role is required")


def _management(context: TenantContext) -> None:
    _scope(context)
    if not context.staff or context.staff.role not in COMPANY_MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Company management approval is required")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _reference(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"


def _payload(row) -> dict:
    data = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, UUID): value = str(value)
        elif isinstance(value, Decimal): value = float(value)
        elif isinstance(value, datetime): value = value.isoformat()
        data[column.name] = value
    return data


class VendorCreate(BaseModel):
    vendor_code: str = Field(min_length=2, max_length=80)
    legal_name: str = Field(min_length=2, max_length=240)
    category: str | None = None
    registration_number: str | None = None
    tax_number: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    risk_rating: str | None = None
    due_diligence_completed: bool = False


class ProcurementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    description: str | None = None
    vendor_id: UUID | None = None
    category: str | None = None
    amount: Decimal = Field(gt=0)


class Decision(BaseModel):
    note: str = Field(min_length=2, max_length=4000)


class BudgetCreate(BaseModel):
    fiscal_year: str = Field(min_length=4, max_length=20)
    version: str = "baseline"
    notes: str | None = None


class BudgetLineCreate(BaseModel):
    cost_centre: str = Field(min_length=2, max_length=100)
    account_code: str = Field(min_length=2, max_length=100)
    period: str = Field(min_length=2, max_length=20)
    budget_amount: Decimal = Decimal("0")
    forecast_amount: Decimal = Decimal("0")
    actual_amount: Decimal = Decimal("0")
    note: str | None = None


class AuditCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    audit_area: str = Field(min_length=2, max_length=120)
    risk_rating: str | None = None
    scope: str | None = None
    lead_auditor_user_id: UUID | None = None


class FindingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    severity: str = "medium"
    observation: str = Field(min_length=3, max_length=6000)
    recommendation: str | None = None
    management_response: str | None = None
    owner_user_id: UUID | None = None
    due_at: datetime | None = None


@router.get("/overview")
def overview(db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    procurement = db.query(ProcurementRequest).filter(ProcurementRequest.company_id == context.company_id)
    budgets = db.query(CompanyBudgetPlan).filter(CompanyBudgetPlan.company_id == context.company_id)
    audits = db.query(InternalAuditEngagement).filter(InternalAuditEngagement.company_id == context.company_id)
    findings = db.query(InternalAuditFinding).filter(InternalAuditFinding.company_id == context.company_id)
    return {
        "procurement": {"pending_approval": procurement.filter(ProcurementRequest.status == "submitted").count()},
        "budgeting": {"draft_plans": budgets.filter(CompanyBudgetPlan.status == "draft").count(), "approved_plans": budgets.filter(CompanyBudgetPlan.status == "approved").count()},
        "internal_audit": {"open_engagements": audits.filter(InternalAuditEngagement.status != "closed").count(), "open_findings": findings.filter(InternalAuditFinding.status != "closed").count()},
    }


@router.post("/vendors", status_code=201)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    if db.query(ProcurementVendor).filter(ProcurementVendor.company_id == context.company_id, ProcurementVendor.vendor_code == payload.vendor_code).first():
        raise HTTPException(status_code=409, detail="Vendor code already exists")
    row = ProcurementVendor(company_id=context.company_id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row); return _payload(row)


@router.get("/procurement")
def list_procurement(db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    q = db.query(ProcurementRequest).filter(ProcurementRequest.company_id == context.company_id)
    if context.branch_id: q = q.filter(ProcurementRequest.branch_id == context.branch_id)
    return [_payload(row) for row in q.order_by(ProcurementRequest.updated_at.desc()).limit(200).all()]


@router.post("/procurement", status_code=201)
def create_procurement(payload: ProcurementCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    if payload.vendor_id and not db.query(ProcurementVendor).filter(ProcurementVendor.id == payload.vendor_id, ProcurementVendor.company_id == context.company_id).first():
        raise HTTPException(status_code=404, detail="Vendor not found in active company")
    row = ProcurementRequest(company_id=context.company_id, branch_id=context.branch_id, reference=_reference("PRC"), requested_by_user_id=context.user.id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row); return _payload(row)


@router.post("/procurement/{request_id}/submit")
def submit_procurement(request_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    row = db.query(ProcurementRequest).filter(ProcurementRequest.id == request_id, ProcurementRequest.company_id == context.company_id).first()
    if not row: raise HTTPException(status_code=404, detail="Procurement request not found")
    if row.status != "draft": raise HTTPException(status_code=409, detail="Only draft requests can be submitted")
    row.status = "submitted"; row.submitted_at = _now(); db.commit(); db.refresh(row); return _payload(row)


@router.post("/procurement/{request_id}/approve")
def approve_procurement(request_id: UUID, payload: Decision, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _management(context)
    row = db.query(ProcurementRequest).filter(ProcurementRequest.id == request_id, ProcurementRequest.company_id == context.company_id).first()
    if not row: raise HTTPException(status_code=404, detail="Procurement request not found")
    if row.status != "submitted": raise HTTPException(status_code=409, detail="Only submitted requests can be approved")
    row.status = "approved"; row.approved_at = _now(); row.approved_by_user_id = context.user.id; row.decision_note = payload.note
    db.commit(); db.refresh(row); return _payload(row)


@router.post("/budgets", status_code=201)
def create_budget(payload: BudgetCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    if db.query(CompanyBudgetPlan).filter(CompanyBudgetPlan.company_id == context.company_id, CompanyBudgetPlan.fiscal_year == payload.fiscal_year, CompanyBudgetPlan.version == payload.version).first():
        raise HTTPException(status_code=409, detail="Budget version already exists for fiscal year")
    row = CompanyBudgetPlan(company_id=context.company_id, branch_id=context.branch_id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row); return _payload(row)


@router.post("/budgets/{plan_id}/lines", status_code=201)
def add_budget_line(plan_id: UUID, payload: BudgetLineCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    plan = db.query(CompanyBudgetPlan).filter(CompanyBudgetPlan.id == plan_id, CompanyBudgetPlan.company_id == context.company_id).first()
    if not plan: raise HTTPException(status_code=404, detail="Budget plan not found")
    if plan.status != "draft": raise HTTPException(status_code=409, detail="Approved budgets are locked")
    row = CompanyBudgetLine(plan_id=plan.id, company_id=context.company_id, branch_id=plan.branch_id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row); return _payload(row)


@router.post("/budgets/{plan_id}/approve")
def approve_budget(plan_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _management(context)
    plan = db.query(CompanyBudgetPlan).filter(CompanyBudgetPlan.id == plan_id, CompanyBudgetPlan.company_id == context.company_id).first()
    if not plan: raise HTTPException(status_code=404, detail="Budget plan not found")
    if not db.query(CompanyBudgetLine.id).filter(CompanyBudgetLine.plan_id == plan.id).first(): raise HTTPException(status_code=409, detail="A budget must contain at least one line before approval")
    plan.status = "approved"; plan.approved_at = _now(); plan.approved_by_user_id = context.user.id
    db.commit(); db.refresh(plan); return _payload(plan)


@router.post("/audits", status_code=201)
def create_audit(payload: AuditCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    row = InternalAuditEngagement(company_id=context.company_id, branch_id=context.branch_id, reference=_reference("AUD"), **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row); return _payload(row)


@router.post("/audits/{engagement_id}/findings", status_code=201)
def create_finding(engagement_id: UUID, payload: FindingCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    engagement = db.query(InternalAuditEngagement).filter(InternalAuditEngagement.id == engagement_id, InternalAuditEngagement.company_id == context.company_id).first()
    if not engagement: raise HTTPException(status_code=404, detail="Audit engagement not found")
    count = db.query(InternalAuditFinding).filter(InternalAuditFinding.engagement_id == engagement.id).count()
    row = InternalAuditFinding(engagement_id=engagement.id, company_id=context.company_id, branch_id=engagement.branch_id, finding_number=f"F-{count + 1:03d}", **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row); return _payload(row)


@router.post("/audits/{engagement_id}/close")
def close_audit(engagement_id: UUID, payload: Decision, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _management(context)
    engagement = db.query(InternalAuditEngagement).filter(InternalAuditEngagement.id == engagement_id, InternalAuditEngagement.company_id == context.company_id).first()
    if not engagement: raise HTTPException(status_code=404, detail="Audit engagement not found")
    open_findings = db.query(InternalAuditFinding).filter(InternalAuditFinding.engagement_id == engagement.id, InternalAuditFinding.status != "closed").count()
    if open_findings: raise HTTPException(status_code=409, detail="Audit cannot close while findings remain open")
    engagement.status = "closed"; engagement.closed_at = _now(); engagement.conclusion = payload.note
    db.commit(); db.refresh(engagement); return _payload(engagement)
