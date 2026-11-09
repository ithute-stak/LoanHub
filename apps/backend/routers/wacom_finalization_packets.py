"""Archive a reviewed Wacom evidence PDF once after independent approval.

This endpoint is NOT legal contract signing. It does not alter a LoanContract.
"""
from __future__ import annotations
import hashlib
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context, require_tenant_roles,
)
from database.models.audit_log import AuditLog
from database.models.file_management import ManagedFile
from database.models.origination import LoanContract
from database.models.wacom_document_intent import WacomDocumentIntent
from database.models.wacom_finalization_approval import WacomFinalizationApproval
from database.models.wacom_finalization_packet import WacomFinalizationPacket
from database.session import get_db
from services.file_service import read_file_bytes, store_bytes
from services.wacom_finalization_preflight import finalization_blockers
from services.wacom_packet_policy import packet_blockers
from services.wacom_pdf_evidence_package import build_review_evidence_pdf


def _gate():
    if os.getenv("LOANHUB_WACOM_PACKET_ARCHIVE_ENABLED", "") != "1":
        raise HTTPException(503, "Wacom review packet archive is disabled")


router = APIRouter(
    prefix="/wacom-finalization-packets",
    tags=["Wacom Archived Review Evidence"],
    dependencies=[Depends(_gate)],
)


@router.post("/approved/{approval_id}", status_code=201)
def archive_approved_evidence(
    approval_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    # Lock approval first to serialize retries and prevent double consumption.
    approval = db.query(WacomFinalizationApproval).filter(
        WacomFinalizationApproval.id == approval_id,
        WacomFinalizationApproval.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if approval is None:
        raise HTTPException(404, "Approved evidence not found")
    # An exact retry returns the existing immutable archive ID, not a new file.
    existing = db.query(WacomFinalizationPacket).filter(
        WacomFinalizationPacket.company_id == ctx.company_id,
        WacomFinalizationPacket.approval_id == approval.id,
    ).one_or_none()
    if existing:
        return {
            "packet_id": str(existing.id), "file_id": str(existing.packet_file_id),
            "pdf_sha256": existing.packet_sha256, "duplicate": True,
            "contract_signed": False, "signing_authorized": False,
        }
    intent = db.query(WacomDocumentIntent).filter(
        WacomDocumentIntent.id == approval.intent_id,
        WacomDocumentIntent.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if intent is None:
        raise HTTPException(409, "Reviewed intent unavailable")
    if packet_blockers(
        approval=approval, intent=intent, executor_id=ctx.user.id,
    ):
        raise HTTPException(409, "Approved review package is expired or invalid")
    # Revalidate contract under lock; other contract signing endpoints may
    # update the contract between a previous reviewer approval and this action.
    contract = db.query(LoanContract).filter(
        LoanContract.id == intent.contract_id,
        LoanContract.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    source = db.query(ManagedFile).filter(
        ManagedFile.id == intent.source_file_id,
        ManagedFile.company_id == ctx.company_id,
    ).one_or_none()
    evidence = db.query(ManagedFile).filter(
        ManagedFile.id == intent.evidence_file_id,
        ManagedFile.company_id == ctx.company_id,
    ).one_or_none()
    if finalization_blockers(intent=intent, contract=contract, source=source, evidence=evidence):
        raise HTTPException(409, "Contract or reviewed evidence no longer eligible")
    source_bytes = read_file_bytes(source)
    ink_bytes = read_file_bytes(evidence)
    packet_bytes, digest = build_review_evidence_pdf(
        source_pdf=source_bytes, source_sha256=intent.document_sha256,
        handwriting_png=ink_bytes, evidence_sha256=intent.evidence_sha256,
        contract_id=str(intent.contract_id), intent_id=str(intent.id),
        binding_sha256=intent.binding_sha256,
        consent_reference=intent.consent_reference,
        review_reference=intent.review_reference,
    )
    if hashlib.sha256(packet_bytes).hexdigest() != digest:
        raise HTTPException(409, "Rendered packet integrity mismatch")
    stored = store_bytes(
        db, content=packet_bytes,
        original_name=f"wacom-review-{intent.id}-NOT-SIGNED.pdf",
        mime_type="application/pdf", owner_user_id=ctx.user.id,
        company_id=ctx.company_id, branch_id=ctx.branch_id,
        category="wacom_review_evidence_packet",
        visibility="private", is_confidential=True,
        description="Approved Wacom evidence package; NOT an executed contract",
        linked_entity_type="wacom_review_intent", linked_entity_id=str(intent.id),
    )
    if stored.scan_status != "clean" or not stored.is_encrypted:
        db.rollback()
        raise HTTPException(503, "Review packet must be malware-scanned and encrypted")
    now = datetime.now(timezone.utc)
    packet = WacomFinalizationPacket(
        id=uuid4(), company_id=ctx.company_id, approval_id=approval.id,
        intent_id=intent.id, contract_id=intent.contract_id,
        packet_file_id=stored.id, source_sha256=intent.document_sha256,
        handwriting_sha256=intent.evidence_sha256, packet_sha256=digest,
        created_by_user_id=ctx.user.id, archived_at=now,
    )
    db.add(packet)
    approval.status = "consumed"
    approval.consumed_at = now
    db.add(AuditLog(
        user_id=ctx.user.id, company_id=ctx.company_id, branch_id=ctx.branch_id,
        action="wacom.review_packet_archived",
        table_name="wacom_finalization_packets",
        entity_type="wacom_review_evidence", record_id=packet.id,
        severity="high", status="success",
        description="Approved Wacom review PDF archived without executing contract",
        event_data={
            "intent_id": str(intent.id), "approval_id": str(approval.id),
            "packet_sha256": digest, "source_sha256": intent.document_sha256,
            "handwriting_sha256": intent.evidence_sha256,
            "contract_signed": False, "reusable_signature": False,
        },
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Reviewed evidence package already archived") from exc
    return {
        "packet_id": str(packet.id), "file_id": str(stored.id),
        "pdf_sha256": digest, "duplicate": False,
        "contract_signed": False, "signing_authorized": False,
    }
