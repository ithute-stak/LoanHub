"""Isolated, exactly-once Wacom final-PDF CANDIDATE archival.

Never interprets visible ink as a legally executed signature. No borrower
signed timestamp, contract status, disbursement or final signing key changes.
Object storage is external to PostgreSQL: reconcile orphan objects after
failed/uncertain commits, never assume distributed ACID transactions.
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
from database.models.wacom_execution_authorization import WacomExecutionAuthorization
from database.models.wacom_execution_receipt import WacomExecutionReceipt
from database.session import get_db
from routers.wacom_execution_authorizations import _locked_sources, _confirm_packet
from routers.wacom_finalization_approvals import _review_sources
from services.file_service import read_file_bytes, store_bytes
from services.wacom_execution_receipt_policy import reserve_execution_blockers
from services.wacom_execution_commit_policy import execution_commit_blockers
from services.wacom_final_pdf_candidate import render_final_pdf_candidate

FLAG = "LOANHUB_WACOM_CANDIDATE_ARCHIVE_ENABLED"


def _gate():
    if os.getenv(FLAG, "") != "1":
        raise HTTPException(503, "Wacom PDF candidate archive is disabled")


router = APIRouter(
    prefix="/wacom-pdf-candidates",
    tags=["Wacom Unexecuted PDF Candidate Archive"],
    dependencies=[Depends(_gate)],
)


def _receipt_response(row, *, duplicate):
    return {
        "receipt_id": str(row.id),
        "candidate_file_id": str(row.executed_file_id),
        "candidate_pdf_sha256": row.executed_pdf_sha256,
        "duplicate": duplicate,
        "status": "candidate_archived_not_signed",
        "contract_signed": False,
        "execution_performed": False,
    }


def _verify_existing(db, ctx, row, intent, authorization):
    if (row.company_id != ctx.company_id or row.intent_id != intent.id
            or row.authorization_id != authorization.id
            or row.contract_id != intent.contract_id
            or row.field_binding_sha256 != authorization.field_binding_sha256
            or row.status != "reserved"
            or row.executed_file_id is None or not row.executed_pdf_sha256):
        raise HTTPException(409, "Existing receipt does not match exact request")
    stored = db.query(ManagedFile).filter(
        ManagedFile.id == row.executed_file_id,
        ManagedFile.company_id == ctx.company_id,
    ).one_or_none()
    if (stored is None or stored.is_deleted or not stored.is_encrypted
            or not stored.is_confidential or stored.scan_status != "clean"
            or stored.category != "wacom_execution_candidate"
            or stored.checksum_sha256 != row.executed_pdf_sha256):
        raise HTTPException(409, "Previously archived candidate cannot be verified")
    if hashlib.sha256(read_file_bytes(stored)).hexdigest() != row.executed_pdf_sha256:
        raise HTTPException(409, "Archived candidate bytes changed")
    return _receipt_response(row, duplicate=True)


@router.post("/authorizations/{authorization_id}/archive", status_code=201)
def archive_pdf_candidate(
    authorization_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)

    # Lock the approval, intent and evidence packet first. They are immutable
    # prerequisites of a specific tenant-scoped execution authorization.
    candidate = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.id == authorization_id,
        WacomExecutionAuthorization.company_id == ctx.company_id,
    ).one_or_none()
    if candidate is None:
        raise HTTPException(404, "Execution authorization unavailable")
    approval, intent, packet = _locked_sources(db, ctx, candidate.intent_id)
    authorization = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.id == authorization_id,
        WacomExecutionAuthorization.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if authorization is None:
        raise HTTPException(404, "Execution authorization unavailable")

    contract = db.query(LoanContract).filter(
        LoanContract.id == intent.contract_id,
        LoanContract.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if contract is None:
        raise HTTPException(409, "Contract unavailable")

    receipt = db.query(WacomExecutionReceipt).filter(
        WacomExecutionReceipt.company_id == ctx.company_id,
        WacomExecutionReceipt.contract_id == intent.contract_id,
    ).with_for_update().one_or_none()
    if receipt is not None:
        return _verify_existing(db, ctx, receipt, intent, authorization)

    # Do not permit replay by the capture/review/approval/archival actors.
    if ctx.user.id in {
        intent.operator_user_id, intent.review_by, approval.requested_by,
        approval.decided_by, packet.created_by_user_id,
        authorization.requested_by, authorization.authorized_by,
    }:
        raise HTTPException(403, "Independent finalization operator required")

    _review_sources(db, ctx, intent)
    _confirm_packet(db, ctx, packet)
    source = db.query(ManagedFile).filter(
        ManagedFile.id == intent.source_file_id,
        ManagedFile.company_id == ctx.company_id,
    ).one_or_none()
    evidence = db.query(ManagedFile).filter(
        ManagedFile.id == intent.evidence_file_id,
        ManagedFile.company_id == ctx.company_id,
    ).one_or_none()
    if source is None or evidence is None:
        raise HTTPException(409, "Source PDF or handwriting evidence unavailable")

    source_pdf = read_file_bytes(source)
    handwriting_png = read_file_bytes(evidence)
    now = datetime.now(timezone.utc)
    blockers = reserve_execution_blockers(
        intent=intent, approval=approval, packet=packet,
        execution_authorization=authorization, contract=contract,
        source=source, evidence=evidence, executing_user_id=ctx.user.id,
        source_pdf=source_pdf, handwriting_png=handwriting_png,
        existing_receipt=None, now=now,
    )
    if blockers:
        raise HTTPException(409, "Wacom PDF candidate archival preflight failed")

    pdf, digest = render_final_pdf_candidate(
        source_pdf=source_pdf, handwriting_png=handwriting_png,
        authorization=authorization,
        expected_source_sha256=intent.document_sha256,
        expected_handwriting_sha256=intent.evidence_sha256,
    )
    if hashlib.sha256(pdf).hexdigest() != digest:
        raise HTTPException(409, "Final PDF candidate hash mismatch")
    stored = store_bytes(
        db, content=pdf, original_name=f"wacom-{intent.id}-CANDIDATE-NOT-SIGNED.pdf",
        mime_type="application/pdf", owner_user_id=ctx.user.id,
        company_id=ctx.company_id, branch_id=ctx.branch_id,
        category="wacom_execution_candidate", visibility="private",
        is_confidential=True,
        description="Approved Wacom visible handwriting PDF candidate: NOT SIGNED",
        linked_entity_type="wacom_document_intent", linked_entity_id=str(intent.id),
    )
    if not stored.is_encrypted or stored.scan_status != "clean":
        db.rollback()
        raise HTTPException(503, "Candidate storage must be encrypted and scanned")

    receipt = WacomExecutionReceipt(
        id=uuid4(), company_id=ctx.company_id, contract_id=intent.contract_id,
        intent_id=intent.id, authorization_id=authorization.id,
        packet_id=packet.id, document_sha256=intent.document_sha256,
        evidence_sha256=intent.evidence_sha256, binding_sha256=intent.binding_sha256,
        field_binding_sha256=authorization.field_binding_sha256,
        status="reserved", reserved_by=ctx.user.id, reserved_at=now,
        executed_file_id=stored.id, executed_pdf_sha256=digest,
        # IMPORTANT: executed_at intentionally remains NULL.
        executed_at=None,
    )
    if execution_commit_blockers(
        intent=intent, approval=approval, packet=packet,
        execution_authorization=authorization, receipt=receipt,
        contract=contract, source=source, evidence=evidence,
        candidate_file=stored, executing_user_id=ctx.user.id,
        source_pdf=source_pdf, handwriting_png=handwriting_png,
        candidate_pdf=read_file_bytes(stored), candidate_sha256=digest, now=now,
    ):
        db.rollback()
        raise HTTPException(409, "Wacom candidate commit validation failed")

    db.add(receipt)
    db.add(AuditLog(
        user_id=ctx.user.id, company_id=ctx.company_id, branch_id=ctx.branch_id,
        action="wacom.pdf_candidate_archived",
        table_name="wacom_execution_receipts",
        entity_type="wacom_pdf_candidate", record_id=receipt.id,
        severity="high", status="success",
        description="Wacom PDF candidate archived; contract NOT executed",
        event_data={
            "contract_id": str(intent.contract_id),
            "authorization_id": str(authorization.id),
            "source_sha256": intent.document_sha256,
            "candidate_sha256": digest,
            "approved_field_sha256": authorization.field_binding_sha256,
            "contract_signed": False, "execution_performed": False,
        },
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Wacom contract candidate already archived") from exc
    return _receipt_response(receipt, duplicate=False)
