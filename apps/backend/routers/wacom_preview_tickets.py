"""Proof-bound preview ticket issuance, disabled by default.

No evidence upload, signature finalization or pen HTTP endpoint. The Go
connector must separately verify Ed25519 signature, scope, enrollment,
revocation and atomic replay protection before SDK access.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_user_context
from database.models.origination import LoanContract
from database.models.pad_signing import ContractPadSigningSession
from database.models.wacom_workstation import (
    WacomWorkstationChallengeRecord, WacomWorkstationEnrollment,
)
from database.session import get_db
from routers.wacom_workstation_challenges import _operator_session, _active_enrollment, _aware
from services.wacom_challenge_persistence import consume_verified_wacom_challenge
from services.wacom_preview_ticket import issue_wacom_preview_ticket
from services.wacom_preview_signing_keys import load_wacom_preview_ticket_signer
from services.wacom_session_revalidation import current_pad_preview_eligibility
from services.wacom_workstation_proof import (
    WacomWorkstationChallenge, verify_enrolled_wacom_workstation_proof,
)

router = APIRouter(prefix="/contract-signing", tags=["Wacom Preview Authorization"])


class PreviewTicketProof(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workstation_id: UUID
    challenge_id: UUID
    signature_base64: str = Field(min_length=86, max_length=88)


@router.post("/contracts/{contract_id}/pad/sessions/{session_id}/preview-tickets")
def authorize_wacom_preview_ticket(
    contract_id: UUID,
    session_id: UUID,
    payload: PreviewTicketProof,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """One-shot authenticated proof -> preview ticket. Never a signing grant."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    # Fail closed before touching/consuming proof if deployment hasn't
    # explicitly configured a pinned, trusted backend Ed25519 signing key.
    signer, key_id = load_wacom_preview_ticket_signer()
    _operator_session(db, context=context, contract_id=contract_id, session_id=session_id)
    # Lock contract and session before rechecking. Cancellation and contract
    # mutation must not race authorization within the same database.
    contract = (
        db.query(LoanContract)
        .filter(LoanContract.id == contract_id, LoanContract.company_id == context.company_id)
        .with_for_update(of=LoanContract)
        .one_or_none()
    )
    session = (
        db.query(ContractPadSigningSession)
        .filter(
            ContractPadSigningSession.id == session_id,
            ContractPadSigningSession.company_id == context.company_id,
            ContractPadSigningSession.contract_id == contract_id,
            ContractPadSigningSession.operator_user_id == context.user.id,
        )
        .with_for_update(of=ContractPadSigningSession)
        .one_or_none()
    )
    if contract is None or session is None:
        raise HTTPException(404, "Pad preview session unavailable")
    now = datetime.now(timezone.utc)
    if not current_pad_preview_eligibility(session, contract, now)["preview_eligible"]:
        raise HTTPException(409, "Pad session is no longer eligible for test preview")
    enrollment = _active_enrollment(
        db, context=context, workstation_id=payload.workstation_id,
    )
    challenge = (
        db.query(WacomWorkstationChallengeRecord)
        .filter(
            WacomWorkstationChallengeRecord.id == payload.challenge_id,
            WacomWorkstationChallengeRecord.company_id == context.company_id,
            WacomWorkstationChallengeRecord.enrollment_id == enrollment.id,
            WacomWorkstationChallengeRecord.session_id == session_id,
            WacomWorkstationChallengeRecord.consumed_at.is_(None),
        )
        .one_or_none()
    )
    if challenge is None:
        raise HTTPException(409, "Unconsumed workstation challenge unavailable")
    try:
        signature = base64.b64decode(payload.signature_base64, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(422, "Invalid workstation proof encoding") from error

    proof = WacomWorkstationChallenge(
        id=challenge.id, workstation_id=enrollment.workstation_id,
        session_id=challenge.session_id,
        nonce=base64.urlsafe_b64encode(bytes(challenge.nonce)).decode("ascii").rstrip("="),
        issued_at=_aware(challenge.expires_at) - timedelta(seconds=30),
        expires_at=_aware(challenge.expires_at),
    )
    try:
        verify_enrolled_wacom_workstation_proof(
            challenge=proof,
            expected_workstation_id=payload.workstation_id,
            expected_session_id=session_id,
            enrolled_public_key=bytes(enrollment.ed25519_public_key),
            signature=signature,
            now=now,
            consume_challenge_once=lambda proof_id: consume_verified_wacom_challenge(
                db, challenge_id=proof_id, company_id=context.company_id,
                enrollment_id=enrollment.id, session_id=session_id, now=now,
            ),
        )
        # Revalidate after consuming one-time proof; any failure rolls back.
        if not current_pad_preview_eligibility(session, contract, datetime.now(timezone.utc))["preview_eligible"]:
            raise HTTPException(409, "Pad preview was revoked")
        ticket = issue_wacom_preview_ticket(
            signing_key=signer, key_id=key_id,
            session=session,
            authenticated_company_id=context.company_id,
            authenticated_operator_id=context.user.id,
            current_contract_id=contract.id,
            current_contract_hash=contract.contract_hash,
            expected_session_id=session.id,
            authorized_workstation_id=enrollment.workstation_id,
            now=datetime.now(timezone.utc),
            lifetime=timedelta(seconds=30),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    # Only operator-authenticated callers can receive this test-preview-only
    # ticket; it must never be sent to an unverified client or into a URL.
    return {
        "preview_ticket": ticket,
        "workstation_id": str(enrollment.workstation_id),
        "session_id": str(session_id),
        "expires_in_seconds_max": 30,
        "capture_enabled": False,
        "contract_signed": False,
    }
