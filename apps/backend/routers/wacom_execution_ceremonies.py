"""Gated Wacom ceremony challenge issuance; NOT hardware attestation or signing.

A securely generated secret is returned only once to an authorized company
operator and only its SHA-256 is persisted. Neither API callers nor a physical
device may claim verification by submitting booleans. This endpoint has NO
verification/consumption path, contract mutations, or signing side effects.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
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
from database.models.wacom_execution_ceremony_challenge import WacomExecutionCeremonyChallenge
from database.session import get_db
from routers.wacom_execution_authorizations import _locked_sources, _confirm_packet
from services.file_service import read_file_bytes
from services.wacom_ceremony_challenge_policy import (
    ceremony_challenge_blockers, challenge_lifetime_blockers,
)

FEATURE_FLAG = "LOANHUB_WACOM_CEREMONY_CHALLENGE_ISSUANCE_ENABLED"


def _gate():
    if os.getenv(FEATURE_FLAG, "") != "1":
        raise HTTPException(503, "Wacom ceremony challenge issuance disabled")


router = APIRouter(
    prefix="/wacom-execution-ceremonies",
    tags=["Wacom Unverified Signing Ceremony Challenge"],
    dependencies=[Depends(_gate)],
)


@router.post("/authorizations/{authorization_id}/challenge", status_code=201)
def issue_ceremony_challenge(
    authorization_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)

    candidate = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.id == authorization_id,
        WacomExecutionAuthorization.company_id == ctx.company_id,
    ).one_or_none()
    if candidate is None:
        raise HTTPException(404, "Wacom execution authorization unavailable")
    # Respect existing lock ordering to avoid deadlocks with archive/approval.
    approval, intent, packet = _locked_sources(db, ctx, candidate.intent_id)
    authorization = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.id == authorization_id,
        WacomExecutionAuthorization.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    if authorization is None:
        raise HTTPException(404, "Wacom execution authorization unavailable")
    contract = db.query(LoanContract).filter(
        LoanContract.id == intent.contract_id,
        LoanContract.company_id == ctx.company_id,
    ).with_for_update().one_or_none()
    receipt = db.query(WacomExecutionReceipt).filter(
        WacomExecutionReceipt.company_id == ctx.company_id,
        WacomExecutionReceipt.contract_id == intent.contract_id,
    ).with_for_update().one_or_none()
    existing = db.query(WacomExecutionCeremonyChallenge).filter(
        WacomExecutionCeremonyChallenge.company_id == ctx.company_id,
        WacomExecutionCeremonyChallenge.contract_id == intent.contract_id,
    ).with_for_update().one_or_none()
    saved = None
    if receipt is not None and receipt.executed_file_id:
        saved = db.query(ManagedFile).filter(
            ManagedFile.company_id == ctx.company_id,
            ManagedFile.id == receipt.executed_file_id,
        ).one_or_none()
    now = datetime.now(timezone.utc)
    if ceremony_challenge_blockers(
        intent=intent, authorization=authorization, receipt=receipt,
        contract=contract, candidate_file=saved,
        requesting_user_id=ctx.user.id,
        existing_challenge=existing, now=now,
    ):
        raise HTTPException(409, "Signing-ceremony challenge prerequisites not met")

    # The candidate must remain backed by reviewed, tenant-scoped evidence.
    # Neither receipt metadata nor an operator-supplied digest is sufficient.
    _confirm_packet(db, ctx, packet)
    if (approval.company_id != ctx.company_id
            or approval.intent_id != intent.id
            or approval.status != "consumed"):
        raise HTTPException(409, "Finalization approval is not archived")
    archived_pdf = read_file_bytes(saved)
    if (len(archived_pdf) > 25 * 1024 * 1024
            or not archived_pdf.startswith(b"%PDF-")
            or hashlib.sha256(archived_pdf).hexdigest() != receipt.executed_pdf_sha256):
        raise HTTPException(409, "Archived PDF candidate integrity mismatch")

    expires = min(
        now + timedelta(minutes=2),
        authorization.expires_at.replace(tzinfo=timezone.utc)
        if authorization.expires_at.tzinfo is None else authorization.expires_at,
    )
    if challenge_lifetime_blockers(requested_at=now, expires_at=expires, now=now):
        raise HTTPException(409, "Execution permit expired")

    # One-use random challenge; persist only the SHA-256 digest.
    # HTTP clients must NOT log or place the secret in URLs/analytics.
    plaintext = secrets.token_urlsafe(48)
    digest = hashlib.sha256(plaintext.encode("ascii")).hexdigest()
    row = WacomExecutionCeremonyChallenge(
        id=uuid4(), company_id=ctx.company_id, borrower_id=intent.borrower_id,
        contract_id=intent.contract_id, intent_id=intent.id,
        authorization_id=authorization.id, receipt_id=receipt.id,
        workstation_id=intent.workstation_id, challenge_sha256=digest,
        candidate_sha256=receipt.executed_pdf_sha256,
        field_binding_sha256=authorization.field_binding_sha256,
        status="pending", requested_by=ctx.user.id,
        requested_at=now, expires_at=expires,
        verified_at=None, consumed_at=None,
    )
    db.add(row)
    db.add(AuditLog(
        user_id=ctx.user.id, company_id=ctx.company_id, branch_id=ctx.branch_id,
        action="wacom.execution_ceremony_challenge_issued",
        table_name="wacom_execution_ceremony_challenges",
        entity_type="wacom_execution_ceremony_challenge", record_id=row.id,
        severity="high", status="success",
        description="Unverified Wacom ceremony challenge issued; contract NOT signed",
        event_data={
            "intent_id": str(intent.id), "contract_id": str(intent.contract_id),
            "authorization_id": str(authorization.id),
            "candidate_sha256": receipt.executed_pdf_sha256,
            "field_binding_sha256": authorization.field_binding_sha256,
            "contract_signed": False, "device_verified": False,
        },
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Signing-ceremony challenge already exists") from exc
    return {
        "challenge_id": str(row.id),
        "challenge_secret": plaintext,
        "company_id": str(ctx.company_id),
        "contract_id": str(intent.contract_id),
        "borrower_id": str(intent.borrower_id),
        "workstation_id": str(intent.workstation_id),
        "candidate_pdf_sha256": row.candidate_sha256,
        "field_binding_sha256": row.field_binding_sha256,
        "expires_at": row.expires_at,
        "status": "pending",
        "device_verified": False,
        "borrower_affirmed": False,
        "contract_signed": False,
        "execution_performed": False,
    }
