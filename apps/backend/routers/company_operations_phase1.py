from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import COMPANY_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_operations_phase1 import (
    CRMRelationshipCase,
    CollateralAsset,
    ComplaintCase,
    CompanyOperationEvent,
    LegalRecoveryMatter,
)
from database.session import get_db

router = APIRouter(prefix="/company-operations", tags=["Specialised Company Operations"])


def _scope(context: TenantContext) -> None:
    require_tenant_roles(context, COMPANY_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=403, detail="A company-scoped role is required")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _reference(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"


def _branch_filter(query, model, context: TenantContext):
    if context.branch_id:
        query = query.filter(model.branch_id == context.branch_id)
    return query


def _loan(db: Session, context: TenantContext, loan_id: UUID | None) -> ClientCompanyLoan | None:
    if not loan_id:
        return None
    query = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == context.company_id,
    )
    if context.branch_id:
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Loan not found in the active company/branch scope")
    return row


def _event(db: Session, context: TenantContext, module: str, record_id: UUID, event_type: str, payload: dict | None = None) -> None:
    db.add(CompanyOperationEvent(
        company_id=context.company_id,
        branch_id=context.branch_id,
        module=module,
        record_id=record_id,
        event_type=event_type,
        actor_user_id=context.user.id,
        payload=payload or {},
    ))


def _payload(row) -> dict:
    data = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, UUID):
            value = str(value)
        elif isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


class CRMCreate(BaseModel):
    borrower_id: UUID
    loan_id: UUID | None = None
    relationship_stage: str = "active"
    segment: str | None = None
    assigned_user_id: UUID | None = None
    next_action_at: datetime | None = None
    contact_preference: str | None = None
    retention_risk: str | None = None
    notes: str | None = Field(default=None, max_length=6000)


class CRMContact(BaseModel):
    note: str = Field(min_length=2, max_length=6000)
    next_action_at: datetime | None = None
    relationship_stage: str | None = None
    retention_risk: str | None = None


class CollateralCreate(BaseModel):
    borrower_id: UUID
    loan_id: UUID | None = None
    asset_type: str = Field(min_length=2, max_length=60)
    description: str = Field(min_length=3, max_length=6000)
    ownership_name: str = Field(min_length=2, max_length=240)
    ownership_reference: str | None = None
    valuation_amount: Decimal | None = None
    valuation_date: datetime | None = None
    valuer_name: str | None = None
    perfected: bool = False
    perfection_reference: str | None = None
    insured: bool = False
    insurance_expiry_at: datetime | None = None


class LegalCreate(BaseModel):
    borrower_id: UUID
    loan_id: UUID
    collection_case_id: UUID | None = None
    legal_stage: str = "pre_action"
    counsel_name: str | None = None
    court_name: str | None = None
    court_case_number: str | None = None
    claim_amount: Decimal | None = None
    legal_costs: Decimal = Decimal("0")
    next_court_at: datetime | None = None
    limitation_deadline_at: datetime | None = None
    assigned_user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=6000)


class LegalStageUpdate(BaseModel):
    legal_stage: str = Field(min_length=2, max_length=50)
    status: str | None = None
    next_court_at: datetime | None = None
    court_case_number: str | None = None
    outcome: str | None = None
    note: str = Field(min_length=2, max_length=6000)


class ComplaintCreate(BaseModel):
    borrower_id: UUID | None = None
    loan_id: UUID | None = None
    category: str = Field(min_length=2, max_length=80)
    channel: str = "internal"
    subject: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=3, max_length=6000)
    severity: str = "normal"
    assigned_user_id: UUID | None = None
    sla_hours: int = Field(default=48, ge=1, le=720)
    regulatory_reportable: bool = False


class ComplaintResolve(BaseModel):
    resolution: str = Field(min_length=3, max_length=6000)
    root_cause: str | None = Field(default=None, max_length=6000)
    remediation: str | None = Field(default=None, max_length=6000)


@router.get("/overview")
def overview(db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    crm = _branch_filter(db.query(CRMRelationshipCase).filter(CRMRelationshipCase.company_id == context.company_id), CRMRelationshipCase, context)
    collateral = _branch_filter(db.query(CollateralAsset).filter(CollateralAsset.company_id == context.company_id), CollateralAsset, context)
    legal = _branch_filter(db.query(LegalRecoveryMatter).filter(LegalRecoveryMatter.company_id == context.company_id), LegalRecoveryMatter, context)
    complaints = _branch_filter(db.query(ComplaintCase).filter(ComplaintCase.company_id == context.company_id), ComplaintCase, context)
    now = _now()
    return {
        "crm": {
            "open": crm.filter(CRMRelationshipCase.status != "closed").count(),
            "followups_due": crm.filter(CRMRelationshipCase.next_action_at.isnot(None), CRMRelationshipCase.next_action_at <= now, CRMRelationshipCase.status != "closed").count(),
            "retention_risk": crm.filter(CRMRelationshipCase.retention_risk.in_(["high", "critical"]), CRMRelationshipCase.status != "closed").count(),
        },
        "collateral": {
            "held": collateral.filter(CollateralAsset.status == "held").count(),
            "unperfected": collateral.filter(CollateralAsset.status == "held", CollateralAsset.perfected.is_(False)).count(),
            "release_requested": collateral.filter(CollateralAsset.status == "release_requested").count(),
        },
        "legal": {
            "open": legal.filter(LegalRecoveryMatter.status.notin_(["closed", "settled"])).count(),
            "court_dates_due": legal.filter(LegalRecoveryMatter.next_court_at.isnot(None), LegalRecoveryMatter.next_court_at <= now + timedelta(days=14), LegalRecoveryMatter.status.notin_(["closed", "settled"])).count(),
            "limitation_attention": legal.filter(LegalRecoveryMatter.limitation_deadline_at.isnot(None), LegalRecoveryMatter.limitation_deadline_at <= now + timedelta(days=30), LegalRecoveryMatter.status.notin_(["closed", "settled"])).count(),
        },
        "complaints": {
            "open": complaints.filter(ComplaintCase.status.notin_(["resolved", "closed"])).count(),
            "sla_breached": complaints.filter(ComplaintCase.sla_due_at < now, ComplaintCase.status.notin_(["resolved", "closed"])).count(),
            "regulatory_reportable": complaints.filter(ComplaintCase.regulatory_reportable.is_(True), ComplaintCase.status.notin_(["resolved", "closed"])).count(),
        },
    }


@router.get("/crm")
def list_crm(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(CRMRelationshipCase).filter(CRMRelationshipCase.company_id == context.company_id), CRMRelationshipCase, context)
    return [_payload(row) for row in query.order_by(CRMRelationshipCase.updated_at.desc()).limit(limit).all()]


@router.post("/crm", status_code=201)
def create_crm(payload: CRMCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    loan = _loan(db, context, payload.loan_id)
    if loan and loan.borrower_id != payload.borrower_id:
        raise HTTPException(status_code=422, detail="Selected loan does not belong to the selected borrower")
    row = CRMRelationshipCase(
        company_id=context.company_id, branch_id=context.branch_id, borrower_id=payload.borrower_id,
        loan_id=payload.loan_id, reference=_reference("CRM"), relationship_stage=payload.relationship_stage,
        segment=payload.segment, assigned_user_id=payload.assigned_user_id, next_action_at=payload.next_action_at,
        contact_preference=payload.contact_preference, retention_risk=payload.retention_risk, notes=payload.notes,
    )
    db.add(row); db.flush(); _event(db, context, "crm", row.id, "created"); db.commit(); db.refresh(row)
    return _payload(row)


@router.post("/crm/{case_id}/contact")
def record_crm_contact(case_id: UUID, payload: CRMContact, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(CRMRelationshipCase).filter(CRMRelationshipCase.id == case_id, CRMRelationshipCase.company_id == context.company_id), CRMRelationshipCase, context)
    row = query.first()
    if not row: raise HTTPException(status_code=404, detail="CRM case not found")
    row.last_contact_at = _now(); row.next_action_at = payload.next_action_at; row.notes = ((row.notes or "") + f"\n[{_now().isoformat()}] {payload.note}").strip()
    if payload.relationship_stage: row.relationship_stage = payload.relationship_stage
    if payload.retention_risk: row.retention_risk = payload.retention_risk
    _event(db, context, "crm", row.id, "contact_recorded", {"note": payload.note}); db.commit(); db.refresh(row)
    return _payload(row)


@router.get("/collateral")
def list_collateral(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(CollateralAsset).filter(CollateralAsset.company_id == context.company_id), CollateralAsset, context)
    return [_payload(row) for row in query.order_by(CollateralAsset.updated_at.desc()).limit(limit).all()]


@router.post("/collateral", status_code=201)
def create_collateral(payload: CollateralCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    loan = _loan(db, context, payload.loan_id)
    if loan and loan.borrower_id != payload.borrower_id:
        raise HTTPException(status_code=422, detail="Selected loan does not belong to the selected borrower")
    row = CollateralAsset(company_id=context.company_id, branch_id=context.branch_id, borrower_id=payload.borrower_id, loan_id=payload.loan_id,
        reference=_reference("COL"), asset_type=payload.asset_type, description=payload.description, ownership_name=payload.ownership_name,
        ownership_reference=payload.ownership_reference, valuation_amount=payload.valuation_amount, valuation_date=payload.valuation_date,
        valuer_name=payload.valuer_name, perfected=payload.perfected, perfection_reference=payload.perfection_reference,
        insured=payload.insured, insurance_expiry_at=payload.insurance_expiry_at)
    db.add(row); db.flush(); _event(db, context, "collateral", row.id, "registered"); db.commit(); db.refresh(row)
    return _payload(row)


@router.post("/collateral/{asset_id}/request-release")
def request_collateral_release(asset_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(CollateralAsset).filter(CollateralAsset.id == asset_id, CollateralAsset.company_id == context.company_id), CollateralAsset, context)
    row = query.first()
    if not row: raise HTTPException(status_code=404, detail="Collateral asset not found")
    if row.status == "released": raise HTTPException(status_code=409, detail="Collateral has already been released")
    row.status = "release_requested"; row.release_requested_at = _now(); _event(db, context, "collateral", row.id, "release_requested"); db.commit(); db.refresh(row)
    return _payload(row)


@router.post("/collateral/{asset_id}/release")
def release_collateral(asset_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(CollateralAsset).filter(CollateralAsset.id == asset_id, CollateralAsset.company_id == context.company_id), CollateralAsset, context)
    row = query.first()
    if not row: raise HTTPException(status_code=404, detail="Collateral asset not found")
    if row.status != "release_requested": raise HTTPException(status_code=409, detail="A release request is required before collateral release")
    loan = _loan(db, context, row.loan_id)
    if loan and Decimal(str(loan.balance or 0)) > 0:
        raise HTTPException(status_code=409, detail="Collateral cannot be released while the linked loan still has an outstanding balance")
    row.status = "released"; row.released_at = _now(); row.released_by_user_id = context.user.id
    _event(db, context, "collateral", row.id, "released"); db.commit(); db.refresh(row)
    return _payload(row)


@router.get("/legal")
def list_legal(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(LegalRecoveryMatter).filter(LegalRecoveryMatter.company_id == context.company_id), LegalRecoveryMatter, context)
    return [_payload(row) for row in query.order_by(LegalRecoveryMatter.updated_at.desc()).limit(limit).all()]


@router.post("/legal", status_code=201)
def create_legal(payload: LegalCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    loan = _loan(db, context, payload.loan_id)
    if not loan or loan.borrower_id != payload.borrower_id:
        raise HTTPException(status_code=422, detail="Selected loan does not belong to the selected borrower")
    row = LegalRecoveryMatter(company_id=context.company_id, branch_id=context.branch_id, borrower_id=payload.borrower_id, loan_id=payload.loan_id,
        collection_case_id=payload.collection_case_id, reference=_reference("LEG"), legal_stage=payload.legal_stage, counsel_name=payload.counsel_name,
        court_name=payload.court_name, court_case_number=payload.court_case_number, claim_amount=payload.claim_amount,
        legal_costs=payload.legal_costs, next_court_at=payload.next_court_at, limitation_deadline_at=payload.limitation_deadline_at,
        assigned_user_id=payload.assigned_user_id, notes=payload.notes)
    db.add(row); db.flush(); _event(db, context, "legal_recovery", row.id, "matter_opened"); db.commit(); db.refresh(row)
    return _payload(row)


@router.post("/legal/{matter_id}/stage")
def update_legal_stage(matter_id: UUID, payload: LegalStageUpdate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(LegalRecoveryMatter).filter(LegalRecoveryMatter.id == matter_id, LegalRecoveryMatter.company_id == context.company_id), LegalRecoveryMatter, context)
    row = query.first()
    if not row: raise HTTPException(status_code=404, detail="Legal recovery matter not found")
    row.legal_stage = payload.legal_stage; row.next_court_at = payload.next_court_at; row.notes = ((row.notes or "") + f"\n[{_now().isoformat()}] {payload.note}").strip()
    if payload.status: row.status = payload.status
    if payload.court_case_number: row.court_case_number = payload.court_case_number
    if payload.outcome: row.outcome = payload.outcome
    _event(db, context, "legal_recovery", row.id, "stage_updated", {"legal_stage": row.legal_stage, "note": payload.note}); db.commit(); db.refresh(row)
    return _payload(row)


@router.get("/complaints")
def list_complaints(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(ComplaintCase).filter(ComplaintCase.company_id == context.company_id), ComplaintCase, context)
    return [_payload(row) for row in query.order_by(ComplaintCase.updated_at.desc()).limit(limit).all()]


@router.post("/complaints", status_code=201)
def create_complaint(payload: ComplaintCreate, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    loan = _loan(db, context, payload.loan_id)
    if loan and payload.borrower_id and loan.borrower_id != payload.borrower_id:
        raise HTTPException(status_code=422, detail="Selected loan does not belong to the selected borrower")
    row = ComplaintCase(company_id=context.company_id, branch_id=context.branch_id, borrower_id=payload.borrower_id, loan_id=payload.loan_id,
        reference=_reference("CMP"), category=payload.category, channel=payload.channel, subject=payload.subject, description=payload.description,
        severity=payload.severity, assigned_user_id=payload.assigned_user_id, sla_due_at=_now() + timedelta(hours=payload.sla_hours),
        regulatory_reportable=payload.regulatory_reportable)
    db.add(row); db.flush(); _event(db, context, "complaints", row.id, "complaint_opened"); db.commit(); db.refresh(row)
    return _payload(row)


@router.post("/complaints/{case_id}/acknowledge")
def acknowledge_complaint(case_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(ComplaintCase).filter(ComplaintCase.id == case_id, ComplaintCase.company_id == context.company_id), ComplaintCase, context)
    row = query.first()
    if not row: raise HTTPException(status_code=404, detail="Complaint not found")
    if not row.acknowledged_at: row.acknowledged_at = _now()
    row.status = "in_review"; _event(db, context, "complaints", row.id, "acknowledged"); db.commit(); db.refresh(row)
    return _payload(row)


@router.post("/complaints/{case_id}/escalate")
def escalate_complaint(case_id: UUID, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(ComplaintCase).filter(ComplaintCase.id == case_id, ComplaintCase.company_id == context.company_id), ComplaintCase, context)
    row = query.first()
    if not row: raise HTTPException(status_code=404, detail="Complaint not found")
    row.escalated_at = _now(); row.status = "escalated"; _event(db, context, "complaints", row.id, "escalated"); db.commit(); db.refresh(row)
    return _payload(row)


@router.post("/complaints/{case_id}/resolve")
def resolve_complaint(case_id: UUID, payload: ComplaintResolve, db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = _branch_filter(db.query(ComplaintCase).filter(ComplaintCase.id == case_id, ComplaintCase.company_id == context.company_id), ComplaintCase, context)
    row = query.first()
    if not row: raise HTTPException(status_code=404, detail="Complaint not found")
    row.status = "resolved"; row.resolved_at = _now(); row.resolution = payload.resolution; row.root_cause = payload.root_cause; row.remediation = payload.remediation
    _event(db, context, "complaints", row.id, "resolved", {"resolution": payload.resolution}); db.commit(); db.refresh(row)
    return _payload(row)


@router.get("/events/{module}/{record_id}")
def list_events(module: str, record_id: UUID, limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), context: TenantContext = Depends(get_user_context)):
    _scope(context)
    query = db.query(CompanyOperationEvent).filter(CompanyOperationEvent.company_id == context.company_id, CompanyOperationEvent.module == module, CompanyOperationEvent.record_id == record_id)
    if context.branch_id: query = query.filter(CompanyOperationEvent.branch_id == context.branch_id)
    return [_payload(row) for row in query.order_by(CompanyOperationEvent.created_at.desc()).limit(limit).all()]
