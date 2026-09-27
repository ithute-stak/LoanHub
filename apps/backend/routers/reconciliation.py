from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    COLLECTIONS_ROLES,
    FINANCE_ROLES,
    TenantContext,
    TRANSPARENCY_ROLES,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.reconciliation import ReconciliationBatch
from database.session import get_db
from services.reconciliation_service import (
    batch_or_404,
    batch_payload,
    close_batch,
    create_batch,
    dashboard,
    export_csv,
    import_csv,
    line_or_404,
    line_payload,
    manual_match,
    reconcile,
    request_adjustment,
    resolve_line,
    summarize_batch,
)


router = APIRouter(prefix="/reconciliation", tags=["Reconciliation Engine"])
VIEW_ROLES = FINANCE_ROLES | COLLECTIONS_ROLES | COMPANY_MANAGEMENT_ROLES | TRANSPARENCY_ROLES
WRITE_ROLES = FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES
ADJUSTMENT_ROLES = FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES


class BatchCreate(BaseModel):
    source_type: str = Field(max_length=40)
    source_reference: str | None = Field(default=None, max_length=180)
    account_reference: str | None = Field(default=None, max_length=180)
    period_start: date
    period_end: date
    currency: str = Field(default="LSL", min_length=3, max_length=3)


class ManualMatchRequest(BaseModel):
    payment_id: UUID
    evidence_note: str = Field(min_length=5, max_length=8000)


class ResolveLineRequest(BaseModel):
    resolution: str = Field(pattern="^(ignored|duplicate)$")
    note: str = Field(min_length=5, max_length=8000)


class AdjustmentRequest(BaseModel):
    adjustment_type: str = Field(min_length=2, max_length=30)
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=5, max_length=8000)


class CloseBatchRequest(BaseModel):
    note: str = Field(min_length=5, max_length=8000)


@router.get("/dashboard")
def reconciliation_dashboard(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, VIEW_ROLES)
    return dashboard(db, context)


@router.get("/batches")
def reconciliation_batches(
    status: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, VIEW_ROLES)
    query = db.query(ReconciliationBatch).filter(ReconciliationBatch.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(ReconciliationBatch.branch_id == context.branch_id)
    if status:
        query = query.filter(ReconciliationBatch.status == status.strip().lower())
    return [batch_payload(row) for row in query.order_by(ReconciliationBatch.created_at.desc()).limit(limit).all()]


@router.post("/batches", status_code=201)
def open_reconciliation_batch(
    payload: BatchCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    return batch_payload(create_batch(
        db,
        context,
        source_type=payload.source_type,
        source_reference=payload.source_reference,
        account_reference=payload.account_reference,
        period_start=payload.period_start,
        period_end=payload.period_end,
        currency=payload.currency,
    ))


@router.get("/batches/{batch_id}")
def reconciliation_batch_detail(
    batch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, VIEW_ROLES)
    return summarize_batch(db, context, batch_or_404(db, context, batch_id))


@router.post("/batches/{batch_id}/import.csv")
async def import_reconciliation_csv(
    batch_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Upload a CSV reconciliation source")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Reconciliation CSV is limited to 10 MB")
    return import_csv(db, context, batch_or_404(db, context, batch_id, lock=True), content)


@router.post("/batches/{batch_id}/reconcile")
def reconcile_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    return reconcile(db, context, batch_or_404(db, context, batch_id, lock=True))


@router.put("/batches/{batch_id}/lines/{line_id}/match")
def manually_match_line(
    batch_id: UUID,
    line_id: UUID,
    payload: ManualMatchRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    batch = batch_or_404(db, context, batch_id, lock=True)
    row = manual_match(
        db,
        context,
        batch,
        line_or_404(db, context, batch_id, line_id),
        payment_id=payload.payment_id,
        evidence_note=payload.evidence_note,
    )
    return line_payload(row)


@router.patch("/batches/{batch_id}/lines/{line_id}/resolve")
def resolve_reconciliation_line(
    batch_id: UUID,
    line_id: UUID,
    payload: ResolveLineRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    batch = batch_or_404(db, context, batch_id, lock=True)
    return line_payload(resolve_line(
        db,
        context,
        batch,
        line_or_404(db, context, batch_id, line_id),
        resolution=payload.resolution,
        note=payload.note,
    ))


@router.post("/batches/{batch_id}/lines/{line_id}/adjustment", status_code=201)
def request_reconciliation_adjustment(
    batch_id: UUID,
    line_id: UUID,
    payload: AdjustmentRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, ADJUSTMENT_ROLES)
    batch = batch_or_404(db, context, batch_id, lock=True)
    adjustment = request_adjustment(
        db,
        context,
        batch,
        line_or_404(db, context, batch_id, line_id),
        adjustment_type=payload.adjustment_type,
        amount=payload.amount,
        reason=payload.reason,
    )
    return {
        "id": str(adjustment.id),
        "status": adjustment.status,
        "approval_request_id": str(adjustment.approval_request_id) if adjustment.approval_request_id else None,
        "amount": float(adjustment.amount),
    }


@router.post("/batches/{batch_id}/close")
def close_reconciliation_batch(
    batch_id: UUID,
    payload: CloseBatchRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, WRITE_ROLES)
    return batch_payload(close_batch(db, context, batch_or_404(db, context, batch_id, lock=True), note=payload.note))


@router.get("/batches/{batch_id}/export.csv")
def export_reconciliation_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, VIEW_ROLES)
    batch = batch_or_404(db, context, batch_id)
    content = export_csv(db, batch)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={batch.batch_reference}-reconciliation.csv"},
    )
