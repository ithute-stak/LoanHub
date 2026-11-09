"""Gated Wacom execution authorization request/decision, never PDF signing.

An approved permit is only input for a later atomic, locked execution flow.
No contract mutations, signing output or disbursement are performed here.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context, require_tenant_roles,
)
from database.models.audit_log import AuditLog
from database.models.file_management import ManagedFile
from database.models.wacom_document_intent import WacomDocumentIntent
from database.models.wacom_finalization_approval import WacomFinalizationApproval
from database.models.wacom_finalization_packet import WacomFinalizationPacket
from database.models.wacom_execution_authorization import WacomExecutionAuthorization
from database.session import get_db
from routers.wacom_finalization_approvals import _review_sources
from services.file_service import read_file_bytes
from services.wacom_approved_field import bind_approved_field, stored_field_matches
from services.wacom_execution_authorization_policy import (
    authorization_request_blockers, authorization_decision_blockers,
)

FEATURE_FLAG = "LOANHUB_WACOM_EXECUTION_AUTHORIZATIONS_ENABLED"


def _gate():
    if os.getenv(FEATURE_FLAG, "") != "1":
        raise HTTPException(503, "Wacom contract execution authorizations disabled")


router = APIRouter(
    prefix="/wacom-execution-authorizations",
    tags=["Wacom Independent Execution Authorizations"],
    dependencies=[Depends(_gate)],
)


class FieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_index: int = Field(ge=0, le=99)
    page_count: int = Field(ge=1, le=100)
    x: float
    y: float
    width: float
    height: float


class AuthorizationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern=r"^(approve|reject)$")
    reference: str = Field(min_length=8, max_length=180)
    exact_document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    exact_field_binding_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _response(row):
    return {
        "authorization_id": str(row.id),
        "company_id": str(row.company_id),
        "intent_id": str(row.intent_id),
        "contract_id": str(row.contract_id),
        "packet_id": str(row.packet_id),
        "field_binding_sha256": row.field_binding_sha256,
        "status": row.status,
        "expires_at": row.expires_at,
        "contract_signed": False,
        "execution_performed": False,
        "signing_keys_released": False,
    }


def _locked_sources(db, ctx, intent_id):
    # Consistent lock order: approval, intent, then packet.
    approval = db.query(WacomFinalizationApproval).filter(
        WacomFinalizationApproval.company_id == ctx.company_id,
        WacomFinalizationApproval.intent_id == intent_id,
    ).with_for_update().one_or_none()
    if approval is None:
        raise HTTPException(404, "Archived approval unavailable")
    intent = db.query(WacomDocumentIntent).filter(
        WacomDocumentIntent.company_id == ctx.company_id,
        WacomDocumentIntent.id == intent_id,
    ).with_for_update().one_or_none()
    if intent is None:
        raise HTTPException(404, "Signing intent unavailable")
    packet = db.query(WacomFinalizationPacket).filter(
        WacomFinalizationPacket.company_id == ctx.company_id,
        WacomFinalizationPacket.intent_id == intent_id,
        WacomFinalizationPacket.approval_id == approval.id,
    ).with_for_update().one_or_none()
    if packet is None:
        raise HTTPException(409, "Verified archived evidence unavailable")
    return approval, intent, packet


def _confirm_packet(db, ctx, packet):
    saved = db.query(ManagedFile).filter(
        ManagedFile.id == packet.packet_file_id,
        ManagedFile.company_id == ctx.company_id,
    ).one_or_none()
    if (saved is None or saved.is_deleted or not saved.is_encrypted
            or not saved.is_confidential or saved.scan_status != "clean"
            or saved.checksum_sha256 != packet.packet_sha256):
        raise HTTPException(409, "Archived packet integrity unavailable")
    packet_bytes = read_file_bytes(saved)
    if hashlib.sha256(packet_bytes).hexdigest() != packet.packet_sha256:
        raise HTTPException(409, "Archived packet content changed")


def _audit(db, ctx, row, action):
    db.add(AuditLog(
        user_id=ctx.user.id, company_id=ctx.company_id, branch_id=ctx.branch_id,
        action=action, table_name="wacom_execution_authorizations",
        entity_type="wacom_execution_authorization", record_id=row.id,
        severity="high", status="success",
        description="Controlled Wacom execution authorization only; no contract signed",
        event_data={
            "intent_id": str(row.intent_id), "contract_id": str(row.contract_id),
            "packet_id": str(row.packet_id), "status": row.status,
            "document_sha256": row.document_sha256,
            "contract_signed": False, "execution_performed": False,
        },
    ))


@router.post("/intents/{intent_id}", status_code=201)
def request_execution_authorization(
    intent_id: UUID,
    body: FieldRequest,
    response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    approval, intent, packet = _locked_sources(db, ctx, intent_id)
    now = datetime.now(timezone.utc)
    if authorization_request_blockers(
        intent=intent, approval=approval, packet=packet,
        requester_id=ctx.user.id, now=now,
    ):
        raise HTTPException(409, "Wacom execution authorization prerequisites not met")
    _review_sources(db, ctx, intent)
    _confirm_packet(db, ctx, packet)
    source_record = db.query(ManagedFile).filter(
        ManagedFile.id == intent.source_file_id,
        ManagedFile.company_id == ctx.company_id,
    ).one_or_none()
    if source_record is None:
        raise HTTPException(409, "Original contract PDF missing")
    try:
        field, field_digest = bind_approved_field(
            source_pdf=read_file_bytes(source_record),
            expected_sha256=intent.document_sha256,
            page_index=body.page_index, expected_page_count=body.page_count,
            x=body.x, y=body.y, width=body.width, height=body.height,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Signature field invalid for approved contract PDF") from exc
    existing = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.company_id == ctx.company_id,
        WacomExecutionAuthorization.contract_id == intent.contract_id,
    ).one_or_none()
    if existing is not None:
        raise HTTPException(409, "Execution authorization already exists for contract")
    # Permit cannot outlive the original consent intent.
    expires_at = min(now + timedelta(minutes=2), intent.expires_at.replace(
        tzinfo=timezone.utc) if intent.expires_at.tzinfo is None else intent.expires_at)
    if expires_at <= now:
        raise HTTPException(409, "Signing intent expired")
    row = WacomExecutionAuthorization(
        id=uuid4(), company_id=ctx.company_id, intent_id=intent.id,
        contract_id=intent.contract_id, packet_id=packet.id,
        document_sha256=intent.document_sha256,
        evidence_sha256=intent.evidence_sha256, binding_sha256=intent.binding_sha256,
        status="pending", requested_by=ctx.user.id,
        requested_at=now, expires_at=expires_at,
        field_page_index=field.page_index, field_page_count=field.page_count,
        field_x=field.x, field_y=field.y,
        field_width=field.width, field_height=field.height,
        field_binding_sha256=field_digest,
    )
    db.add(row)
    _audit(db, ctx, row, "wacom.execution_authorization_requested")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Execution authorization already exists") from exc
    return _response(row)


@router.post("/{authorization_id}/decision")
def decide_execution_authorization(
    authorization_id: UUID,
    body: AuthorizationDecision,
    response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    candidate = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.id == authorization_id,
        WacomExecutionAuthorization.company_id == ctx.company_id,
    ).one_or_none()
    if candidate is None:
        raise HTTPException(404, "Execution authorization not found")
    approval, intent, packet = _locked_sources(db, ctx, candidate.intent_id)
    row = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.id == authorization_id,
        WacomExecutionAuthorization.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(404, "Execution authorization not found")
    now = datetime.now(timezone.utc)
    if authorization_decision_blockers(
        intent=intent, approval=approval, packet=packet,
        authorization=row, approver_id=ctx.user.id, now=now,
    ):
        raise HTTPException(409, "Authorization invalid, expired or not independent")
    if body.exact_document_sha256 != row.document_sha256:
        raise HTTPException(409, "Exact document confirmation mismatch")
    if body.exact_field_binding_sha256 != row.field_binding_sha256:
        raise HTTPException(409, "Approved signature field confirmation mismatch")
    source_record = db.query(ManagedFile).filter(
        ManagedFile.id == intent.source_file_id,
        ManagedFile.company_id == ctx.company_id,
    ).one_or_none()
    if source_record is None or not stored_field_matches(
        authorization=row, source_pdf=read_file_bytes(source_record),
        expected_sha256=intent.document_sha256,
    ):
        raise HTTPException(409, "Signature field or source PDF changed")
    _review_sources(db, ctx, intent)
    _confirm_packet(db, ctx, packet)
    row.status = "approved" if body.decision == "approve" else "rejected"
    row.authorized_by = ctx.user.id
    row.authorized_at = now
    row.authorization_reference = body.reference
    _audit(db, ctx, row, "wacom.execution_authorization_decided")
    db.commit()
    return _response(row)
