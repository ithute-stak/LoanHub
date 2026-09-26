from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_user_context,
    require_tenant_roles,
)
from database.models.collection_automation import CollectionTreatmentPolicy, CollectionWorkItem
from database.models.lending_operations import CollectionCase
from database.session import get_db
from services.collection_automation_service import (
    complete_work_item,
    dashboard,
    get_or_create_policy,
    legal_readiness,
    run_automation,
    update_policy,
    work_item_payload,
)


router = APIRouter(prefix="/collections/automation", tags=["Automated Collections & Recovery"])
VIEW_ROLES = COMPANY_MANAGEMENT_ROLES | COLLECTIONS_ROLES
ACTION_ROLES = VIEW_ROLES


class TreatmentPolicyUpdate(BaseModel):
    strategy: dict[str, Any]


class WorkItemComplete(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class WorkItemAssign(BaseModel):
    assigned_to_user_id: UUID | None = None


class LegalEscalation(BaseModel):
    override_readiness: bool = False
    override_reason: str | None = Field(default=None, max_length=4000)


def _scope(context: TenantContext) -> None:
    require_tenant_roles(context, VIEW_ROLES)
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=403, detail="A company-scoped collections role is required")


def _policy_payload(row: CollectionTreatmentPolicy) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "version": row.version,
        "is_active": bool(row.is_active),
        "strategy": dict(row.strategy or {}),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _work_item_or_404(db: Session, context: TenantContext, item_id: UUID) -> CollectionWorkItem:
    query = db.query(CollectionWorkItem).filter(
        CollectionWorkItem.id == item_id,
        CollectionWorkItem.company_id == context.company_id,
    )
    if context.branch_id:
        query = query.filter(CollectionWorkItem.branch_id == context.branch_id)
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Collection work item not found")
    return row


def _case_or_404(db: Session, context: TenantContext, case_id: UUID) -> CollectionCase:
    query = db.query(CollectionCase).filter(
        CollectionCase.id == case_id,
        CollectionCase.company_id == context.company_id,
    )
    if context.branch_id:
        query = query.filter(CollectionCase.branch_id == context.branch_id)
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Collection case not found")
    return row


@router.get("/dashboard")
def collections_automation_dashboard(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    return dashboard(db, context)


@router.post("/run")
def run_collections_automation(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    run = run_automation(db, context)
    return {
        "id": str(run.id),
        "run_reference": run.run_reference,
        "cases_checked": run.cases_checked,
        "work_items_created": run.work_items_created,
        "work_items_updated": run.work_items_updated,
        "broken_promises_detected": run.broken_promises_detected,
        "legal_ready_cases": run.legal_ready_cases,
        "summary": dict(run.summary or {}),
        "completed_at": run.completed_at.isoformat(),
    }


@router.get("/policy")
def get_collections_policy(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    row = get_or_create_policy(db, context)
    db.commit()
    db.refresh(row)
    return _policy_payload(row)


@router.put("/policy")
def put_collections_policy(
    payload: TreatmentPolicyUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | COLLECTIONS_ROLES)
    return _policy_payload(update_policy(db, context, payload.strategy))


@router.get("/work-items")
def list_collection_work_items(
    status: str | None = Query(default=None),
    assigned_to_me: bool = False,
    recovery_path: str | None = None,
    limit: int = Query(default=250, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    query = db.query(CollectionWorkItem).filter(CollectionWorkItem.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(CollectionWorkItem.branch_id == context.branch_id)
    if status:
        query = query.filter(CollectionWorkItem.status == status)
    if assigned_to_me:
        query = query.filter(CollectionWorkItem.assigned_to_user_id == context.user.id)
    if recovery_path:
        query = query.filter(CollectionWorkItem.recovery_path == recovery_path)
    rows = query.order_by(CollectionWorkItem.priority_score.desc(), CollectionWorkItem.due_at.asc()).limit(limit).all()
    return [work_item_payload(db, row) for row in rows]


@router.put("/work-items/{item_id}/assignment")
def assign_collection_work_item(
    item_id: UUID,
    payload: WorkItemAssign,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    row = _work_item_or_404(db, context, item_id)
    row.assigned_to_user_id = payload.assigned_to_user_id
    case = _case_or_404(db, context, row.case_id)
    case.assigned_to_user_id = payload.assigned_to_user_id
    db.commit()
    db.refresh(row)
    return work_item_payload(db, row)


@router.post("/work-items/{item_id}/complete")
def finish_collection_work_item(
    item_id: UUID,
    payload: WorkItemComplete,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    return work_item_payload(db, complete_work_item(db, context, _work_item_or_404(db, context, item_id), payload.notes))


@router.get("/cases/{case_id}/legal-readiness")
def get_legal_readiness(
    case_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    case = _case_or_404(db, context, case_id)
    return {
        "case_id": str(case.id),
        "case_reference": case.case_reference,
        **legal_readiness(db, case),
    }


@router.post("/cases/{case_id}/escalate-legal")
def escalate_case_to_legal(
    case_id: UUID,
    payload: LegalEscalation,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _scope(context)
    case = _case_or_404(db, context, case_id)
    readiness = legal_readiness(db, case)
    if not readiness["ready"]:
        if not payload.override_readiness:
            raise HTTPException(
                status_code=409,
                detail={"message": "Legal handover checklist is incomplete", "missing": readiness["missing"]},
            )
        if len((payload.override_reason or "").strip()) < 10:
            raise HTTPException(status_code=422, detail="A detailed readiness-override reason is required")
    case.stage = "legal"
    case.status = "legal"
    case.legal_handover_at = datetime.now(timezone.utc)
    note = (payload.override_reason or "").strip()
    if note:
        case.notes = "\n\n".join(value for value in [case.notes, f"Legal readiness override: {note}"] if value)
    db.commit()
    return {
        "case_id": str(case.id),
        "case_reference": case.case_reference,
        "status": case.status,
        "stage": case.stage,
        "legal_handover_at": case.legal_handover_at.isoformat(),
        "readiness": readiness,
    }
