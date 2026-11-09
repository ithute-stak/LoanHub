"""Read-only verification of archived Wacom PDF candidates; NOT legal signing."""
from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context, require_tenant_roles,
)
from database.models.file_management import ManagedFile
from database.models.origination import LoanContract
from database.models.wacom_document_intent import WacomDocumentIntent
from database.models.wacom_finalization_approval import WacomFinalizationApproval
from database.models.wacom_finalization_packet import WacomFinalizationPacket
from database.models.wacom_execution_authorization import WacomExecutionAuthorization
from database.models.wacom_execution_receipt import WacomExecutionReceipt
from database.session import get_db
from services.file_service import read_file_bytes
from services.wacom_candidate_archive_integrity import candidate_archive_blockers

FLAG = "LOANHUB_WACOM_CANDIDATE_VERIFICATION_ENABLED"


def _gate():
    if os.getenv(FLAG, "") != "1":
        raise HTTPException(503, "Wacom candidate verification unavailable")


router = APIRouter(
    prefix="/wacom-pdf-candidate-verification",
    tags=["Wacom Archived Candidate Integrity"],
    dependencies=[Depends(_gate)],
)


def _row(db, model, company_id, record_id):
    return db.query(model).filter(
        model.id == record_id,
        model.company_id == company_id,
    ).one_or_none()


def _file(db, company_id, file_id):
    return _row(db, ManagedFile, company_id, file_id) if file_id else None


@router.get("/receipts/{receipt_id}")
def verify_candidate(
    receipt_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    receipt = _row(db, WacomExecutionReceipt, ctx.company_id, receipt_id)
    if receipt is None:
        raise HTTPException(404, "Archived Wacom receipt not found")

    intent = _row(db, WacomDocumentIntent, ctx.company_id, receipt.intent_id)
    approval = None
    packet = _row(db, WacomFinalizationPacket, ctx.company_id, receipt.packet_id)
    authorization = _row(
        db, WacomExecutionAuthorization, ctx.company_id, receipt.authorization_id,
    )
    contract = _row(db, LoanContract, ctx.company_id, receipt.contract_id)
    if packet is not None:
        approval = _row(db, WacomFinalizationApproval, ctx.company_id, packet.approval_id)

    source = _file(db, ctx.company_id, intent.source_file_id) if intent else None
    ink = _file(db, ctx.company_id, intent.evidence_file_id) if intent else None
    evidence_packet = _file(db, ctx.company_id, packet.packet_file_id) if packet else None
    candidate = _file(db, ctx.company_id, receipt.executed_file_id)
    if any(item is None for item in (
        intent, approval, packet, authorization, contract,
        source, ink, evidence_packet, candidate,
    )):
        return {
            "receipt_id": str(receipt.id),
            "integrity_verified": False,
            "failure_codes": ["archive_chain_missing"],
            "contract_signed": False,
            "legal_execution_verified": False,
        }
    payloads = []
    for file in (source, ink, evidence_packet, candidate):
        try:
            payloads.append(read_file_bytes(file))
        except HTTPException:
            return {
                "receipt_id": str(receipt.id),
                "integrity_verified": False,
                "failure_codes": ["archived_file_unavailable"],
                "contract_signed": False,
                "legal_execution_verified": False,
            }

    failures = candidate_archive_blockers(
        receipt=receipt, intent=intent, approval=approval,
        packet=packet, authorization=authorization, contract=contract,
        source_file=source, evidence_file=ink, packet_file=evidence_packet,
        candidate_file=candidate, source_pdf=payloads[0],
        handwriting_png=payloads[1], packet_pdf=payloads[2],
        candidate_pdf=payloads[3],
    )
    return {
        "receipt_id": str(receipt.id),
        "integrity_verified": not failures,
        "failure_codes": failures,
        "source_sha256": intent.document_sha256,
        "candidate_sha256": receipt.executed_pdf_sha256,
        "field_binding_sha256": receipt.field_binding_sha256,
        "contract_signed": False,
        "legal_execution_verified": False,
    }
