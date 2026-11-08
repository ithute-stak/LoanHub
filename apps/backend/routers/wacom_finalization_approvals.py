"""Management-only two-person PDF finalization approval (NOT execution).

Separately feature gated; no contract status changes or signing key access.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context,
    require_tenant_roles,
)
from database.models.wacom_document_intent import WacomDocumentIntent
from database.models.wacom_finalization_approval import WacomFinalizationApproval
from database.models.origination import LoanContract
from database.models.file_management import ManagedFile
from database.session import get_db
from routers.wacom_document_intents import _verified_source_pdf
from services.wacom_finalization_preflight import finalization_blockers
from services.wacom_approval_policy import approval_blockers


def _gate():
    if os.getenv("LOANHUB_WACOM_FINAL_APPROVALS_ENABLED", "") != "1":
        raise HTTPException(503, "Wacom finalization approvals are disabled")


router = APIRouter(
    prefix="/wacom-finalization-approvals",
    tags=["Wacom Two-Person Finalization Approval"],
    dependencies=[Depends(_gate)],
)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern=r"^(approve|reject)$")
    reference: str = Field(min_length=4, max_length=180)
    reason: str = Field(min_length=8, max_length=400)
    exact_document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _review_sources(db, ctx, intent):
    # Read-only references, protected by an intent row lock in callers.
    contract = db.query(LoanContract).filter(
        LoanContract.company_id == ctx.company_id,
        LoanContract.id == intent.contract_id,
    ).one_or_none()
    source = db.query(ManagedFile).filter(
        ManagedFile.company_id == ctx.company_id,
        ManagedFile.id == intent.source_file_id,
    ).one_or_none()
    evidence = None
    if intent.evidence_file_id:
        evidence = db.query(ManagedFile).filter(
            ManagedFile.company_id == ctx.company_id,
            ManagedFile.id == intent.evidence_file_id,
        ).one_or_none()
    blockers = finalization_blockers(
        intent=intent, contract=contract, source=source, evidence=evidence,
    )
    if blockers:
        raise HTTPException(409, "Reviewed evidence or contract is not eligible")
    _verified_source_pdf(source, expected_sha256=intent.document_sha256)
    return contract


def _intent(db, ctx, intent_id):
    row = db.query(WacomDocumentIntent).filter(
        WacomDocumentIntent.id == intent_id,
        WacomDocumentIntent.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(404, "Wacom document intent unavailable")
    return row


def _body(row):
    return {
        "approval_id": str(row.id),
        "intent_id": str(row.intent_id),
        "contract_id": str(row.contract_id),
        "status": row.status,
        "document_sha256": row.document_sha256,
        "expires_at": row.expires_at,
        "contract_signed": False,
        "execution_authorized": False,
        "signing_keys_released": False,
    }


@router.post("/intents/{intent_id}", status_code=201)
def request_approval(
    intent_id: UUID, response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    row = _intent(db, ctx, intent_id)
    if ctx.user.id in (row.operator_user_id, row.review_by):
        raise HTTPException(403, "Request must be independent of capture and evidence review")
    _review_sources(db, ctx, row)
    existing = db.query(WacomFinalizationApproval).filter(
        WacomFinalizationApproval.company_id == ctx.company_id,
        WacomFinalizationApproval.intent_id == intent_id,
    ).one_or_none()
    if existing is not None:
        raise HTTPException(409, "Finalization approval already requested for this document intent")
    now = datetime.now(timezone.utc)
    approval = WacomFinalizationApproval(
        id=uuid4(), company_id=ctx.company_id, intent_id=row.id,
        contract_id=row.contract_id, document_sha256=row.document_sha256,
        evidence_sha256=row.evidence_sha256, binding_sha256=row.binding_sha256,
        requested_by=ctx.user.id, requested_at=now,
        expires_at=now+timedelta(minutes=5), status="pending",
    )
    db.add(approval)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Approval already requested") from exc
    return _body(approval)


@router.post("/{approval_id}/decision")
def decide_approval(
    approval_id: UUID, body: Decision, response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    row = db.query(WacomFinalizationApproval).filter(
        WacomFinalizationApproval.id == approval_id,
        WacomFinalizationApproval.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(404, "Approval unavailable")
    intent = _intent(db, ctx, row.intent_id)
    blockers = approval_blockers(intent=intent, approval=row, approver_id=ctx.user.id)
    if blockers:
        raise HTTPException(409, "Approval invalid, expired or not independently authorized")
    if body.exact_document_sha256 != row.document_sha256:
        raise HTTPException(409, "Exact PDF hash confirmation mismatch")
    _review_sources(db, ctx, intent)
    row.status = "approved" if body.decision == "approve" else "rejected"
    row.decided_by = ctx.user.id
    row.decided_at = datetime.now(timezone.utc)
    row.decision_reference = body.reference
    row.decision_reason = body.reason
    db.commit()
    # A record of approval is NOT a signing credential. No contract mutation.
    return _body(row)
