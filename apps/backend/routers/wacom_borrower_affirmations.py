"""Authenticated borrower review and affirmation of an exact Wacom PDF candidate.

The borrower may read the PDF candidate and explicitly affirm its hash from
their OWN LoanHub borrower account. The service records a limited affirmation,
NOT a legally signed contract, cryptographic device pen attestation or release
of loan funds. Enabled only by a separate deployment feature flag.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import Literal

from core.access_control import TenantContext, get_user_context
from database.models.user import User
from database.models.enums import UserRole
from database.models.borrower import Borrower
from database.models.file_management import ManagedFile
from database.models.audit_log import AuditLog
from database.models.wacom_execution_authorization import WacomExecutionAuthorization
from database.models.wacom_execution_receipt import WacomExecutionReceipt
from database.models.wacom_execution_ceremony_challenge import WacomExecutionCeremonyChallenge
from database.session import get_db
from services.file_service import read_file_bytes
from services.wacom_borrower_affirmation_policy import (
    borrower_affirmation_blockers, affirmation_digest,
)

FLAG = "LOANHUB_WACOM_BORROWER_AFFIRMATION_ENABLED"


def _gate():
    if os.getenv(FLAG, "") != "1":
        raise HTTPException(503, "Wacom borrower affirmation disabled")


router = APIRouter(
    prefix="/wacom-borrower-affirmations",
    tags=["Wacom Borrower PDF Review — Not Signed"],
    dependencies=[Depends(_gate)],
)


class AffirmCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    affirmative_choice: Literal[True]
    displayed_candidate_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    displayed_field_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _borrower(db: Session, current_user):
    if current_user.role != UserRole.BORROWER:
        raise HTTPException(403, "Borrower account authentication required")
    borrower = db.query(Borrower).filter(Borrower.user_id == current_user.id).one_or_none()
    if borrower is None:
        raise HTTPException(403, "Authenticated borrower profile required")
    return borrower


def _records(db: Session, borrower, challenge_id, *, lock=False):
    query = db.query(WacomExecutionCeremonyChallenge).filter(
        WacomExecutionCeremonyChallenge.id == challenge_id,
        WacomExecutionCeremonyChallenge.borrower_id == borrower.id,
    )
    challenge = (query.with_for_update() if lock else query).one_or_none()
    if challenge is None:
        raise HTTPException(404, "Borrower ceremony unavailable")
    authorization = db.query(WacomExecutionAuthorization).filter(
        WacomExecutionAuthorization.id == challenge.authorization_id,
        WacomExecutionAuthorization.company_id == challenge.company_id,
    ).one_or_none()
    receipt = db.query(WacomExecutionReceipt).filter(
        WacomExecutionReceipt.id == challenge.receipt_id,
        WacomExecutionReceipt.company_id == challenge.company_id,
    ).one_or_none()
    candidate = None
    if receipt is not None and receipt.executed_file_id:
        candidate = db.query(ManagedFile).filter(
            ManagedFile.id == receipt.executed_file_id,
            ManagedFile.company_id == challenge.company_id,
        ).one_or_none()
    return challenge, authorization, receipt, candidate


def _verified_bytes(candidate):
    if (candidate is None or not candidate.is_encrypted or candidate.is_deleted
            or not candidate.is_confidential or candidate.scan_status != "clean"
            or candidate.mime_type != "application/pdf"
            or candidate.category != "wacom_execution_candidate"
            or not isinstance(candidate.size_bytes, int)
            or not 5 <= candidate.size_bytes <= 25 * 1024 * 1024):
        raise HTTPException(409, "Verified PDF candidate unavailable")
    pdf = read_file_bytes(candidate)
    if (len(pdf) != candidate.size_bytes or not pdf.startswith(b"%PDF-")
            or hashlib.sha256(pdf).hexdigest() != candidate.checksum_sha256):
        raise HTTPException(409, "Archived PDF candidate integrity mismatch")
    return pdf


def _check(*, db, borrower, challenge_id, user_id, lock, displayed_candidate_sha256,
           displayed_field_sha256):
    challenge, authorization, receipt, candidate = _records(
        db, borrower, challenge_id, lock=lock,
    )
    pdf = _verified_bytes(candidate)
    now = datetime.now(timezone.utc)
    if borrower_affirmation_blockers(
        challenge=challenge, borrower=borrower, authorization=authorization,
        receipt=receipt, candidate_file=candidate, user_id=user_id,
        candidate_pdf=pdf, displayed_candidate_sha256=displayed_candidate_sha256,
        displayed_field_sha256=displayed_field_sha256, now=now,
    ):
        raise HTTPException(409, "Borrower affirmation prerequisites unavailable")
    return challenge, pdf, now


@router.get("/challenges/{challenge_id}/document")
def review_candidate_pdf(
    challenge_id: UUID,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_user_context),
):
    borrower = _borrower(db, ctx.user)
    challenge, authorization, receipt, candidate = _records(db, borrower, challenge_id)
    pdf = _verified_bytes(candidate)
    if borrower_affirmation_blockers(
        challenge=challenge, borrower=borrower, authorization=authorization,
        receipt=receipt, candidate_file=candidate, user_id=ctx.user.id,
        candidate_pdf=pdf, displayed_candidate_sha256=challenge.candidate_sha256,
        displayed_field_sha256=challenge.field_binding_sha256,
    ):
        raise HTTPException(409, "Borrower review document unavailable")
    return StreamingResponse(
        BytesIO(pdf), media_type="application/pdf",
        headers={
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "Content-Disposition": 'inline; filename="loanhub-contract-review-NOT-SIGNED.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/challenges/{challenge_id}/affirm")
def affirm_exact_candidate(
    challenge_id: UUID,
    body: AffirmCandidate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    borrower = _borrower(db, current_user)
    challenge, _, now = _check(
        db=db, borrower=borrower, challenge_id=challenge_id,
        user_id=current_user.id, lock=True,
        displayed_candidate_sha256=body.displayed_candidate_sha256,
        displayed_field_sha256=body.displayed_field_sha256,
    )
    challenge.borrower_affirmed_user_id = ctx.user.id
    challenge.borrower_affirmed_at = now
    challenge.borrower_affirmation_sha256 = affirmation_digest(
        challenge_id=challenge.id, user_id=current_user.id,
        candidate_sha256=body.displayed_candidate_sha256,
        field_sha256=body.displayed_field_sha256, now=now,
    )
    db.add(AuditLog(
        user_id=ctx.user.id, company_id=challenge.company_id,
        action="wacom.borrower_pdf_candidate_affirmed",
        table_name="wacom_execution_ceremony_challenges",
        entity_type="wacom_execution_ceremony_challenge",
        record_id=challenge.id, severity="high", status="success",
        description="Borrower account affirmed PDF candidate; not physical signing",
        event_data={
            "contract_id": str(challenge.contract_id),
            "borrower_id": str(challenge.borrower_id),
            "candidate_sha256": challenge.candidate_sha256,
            "field_binding_sha256": challenge.field_binding_sha256,
            "affirmation_sha256": challenge.borrower_affirmation_sha256,
            "contract_signed": False, "physical_pen_verified": False,
        },
    ))
    if datetime.now(timezone.utc) >= challenge.expires_at:
        db.rollback()
        raise HTTPException(409, "Borrower confirmation expired before commit")
    db.commit()
    return {
        "challenge_id": str(challenge.id),
        "borrower_affirmation_recorded": True,
        "physical_pen_verified": False,
        "legally_executed": False,
        "contract_signed": False,
    }
