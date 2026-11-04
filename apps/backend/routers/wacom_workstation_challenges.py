"""Operator-authenticated, preview-only workstation proof challenge routes.

These routes prove possession of an enrolled public key. They do NOT
issue capture tickets, return pen data, verify borrower identity, record
consent, or sign a document.
"""
from __future__ import annotations

import base64
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_user_context,
    require_tenant_roles,
)
from database.models.enums import UserRole
from database.models.origination import LoanContract
from database.models.pad_signing import ContractPadSigningSession
from database.models.wacom_workstation import (
    WacomWorkstationChallengeRecord,
    WacomWorkstationEnrollment,
)
from database.session import get_db
from services.wacom_challenge_persistence import consume_verified_wacom_challenge
from services.wacom_session_revalidation import current_pad_preview_eligibility
from services.wacom_workstation_proof import (
    WacomWorkstationChallenge,
    verify_enrolled_wacom_workstation_proof,
)

router = APIRouter(prefix="/contract-signing", tags=["Wacom Workstation Verification"])

_ALLOWED_ROLES = LENDING_ROLES | COMPANY_MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
}


class WorkstationChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workstation_id: UUID


class WorkstationProofRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    workstation_id: UUID
    signature_base64: str = Field(min_length=86, max_length=88)


def _aware(value: datetime) -> datetime:
    # Existing project's generic audit created_at is naive UTC in PostgreSQL.
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _operator_session(
    db: Session, *, context: TenantContext, contract_id: UUID, session_id: UUID,
) -> tuple[LoanContract, ContractPadSigningSession]:
    require_tenant_roles(context, _ALLOWED_ROLES)
    contract = (
        db.query(LoanContract)
        .filter(
            LoanContract.id == contract_id,
            LoanContract.company_id == context.company_id,
        )
        .one_or_none()
    )
    if contract is None:
        raise HTTPException(404, "Contract unavailable")
    # Contract branch is checked via existing tenant authorization.
    loan = contract.loan
    assert_branch_scope(context, loan.branch_id if loan else None)
    session = (
        db.query(ContractPadSigningSession)
        .filter(
            ContractPadSigningSession.id == session_id,
            ContractPadSigningSession.company_id == context.company_id,
            ContractPadSigningSession.contract_id == contract_id,
            ContractPadSigningSession.operator_user_id == context.user.id,
        )
        .one_or_none()
    )
    if session is None:
        raise HTTPException(404, "Pad session unavailable")
    if not current_pad_preview_eligibility(
        session, contract, datetime.now(timezone.utc),
    )["preview_eligible"]:
        raise HTTPException(409, "Pad session is not eligible for temporary preview")
    return contract, session


def _active_enrollment(
    db: Session, *, context: TenantContext, workstation_id: UUID,
) -> WacomWorkstationEnrollment:
    row = (
        db.query(WacomWorkstationEnrollment)
        .filter(
            WacomWorkstationEnrollment.company_id == context.company_id,
            WacomWorkstationEnrollment.operator_user_id == context.user.id,
            WacomWorkstationEnrollment.workstation_id == workstation_id,
            WacomWorkstationEnrollment.status == "active",
            WacomWorkstationEnrollment.approved_at.is_not(None),
            WacomWorkstationEnrollment.revoked_at.is_(None),
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(403, "No active enrolled workstation for this operator")
    return row


@router.post(
    "/contracts/{contract_id}/pad/sessions/{session_id}/workstation-challenges",
    status_code=201,
)
def create_wacom_workstation_challenge(
    contract_id: UUID,
    session_id: UUID,
    payload: WorkstationChallengeRequest,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Create an enrolled-workstation challenge, NOT a capture permission."""
    response.headers["Cache-Control"] = "no-store"
    _operator_session(db, context=context, contract_id=contract_id, session_id=session_id)
    enrollment = _active_enrollment(
        db, context=context, workstation_id=payload.workstation_id,
    )
    now = datetime.now(timezone.utc)
    nonce = secrets.token_bytes(32)
    challenge_id = uuid4()
    expires_at = now + timedelta(seconds=30)
    row = WacomWorkstationChallengeRecord(
        id=challenge_id,
        company_id=context.company_id,
        enrollment_id=enrollment.id,
        session_id=session_id,
        nonce=nonce,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    return {
        "challenge_id": str(challenge_id),
        "workstation_id": str(payload.workstation_id),
        "session_id": str(session_id),
        "nonce": base64.urlsafe_b64encode(nonce).decode("ascii").rstrip("="),
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "capture_enabled": False,
    }


@router.post("/contracts/{contract_id}/pad/sessions/{session_id}/workstation-proofs")
def verify_wacom_workstation_proof(
    contract_id: UUID,
    session_id: UUID,
    payload: WorkstationProofRequest,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Consume one valid proof, but never grant capture or signing permission."""
    response.headers["Cache-Control"] = "no-store"
    # Lock parent contract/session to serialize cancellation and modification
    # in this transaction. A future capture-ticket route MUST revalidate again.
    _operator_session(db, context=context, contract_id=contract_id, session_id=session_id)
    enrollment = _active_enrollment(
        db, context=context, workstation_id=payload.workstation_id,
    )
    row = (
        db.query(WacomWorkstationChallengeRecord)
        .filter(
            WacomWorkstationChallengeRecord.id == payload.challenge_id,
            WacomWorkstationChallengeRecord.company_id == context.company_id,
            WacomWorkstationChallengeRecord.enrollment_id == enrollment.id,
            WacomWorkstationChallengeRecord.session_id == session_id,
        )
        .one_or_none()
    )
    if row is None or row.consumed_at is not None:
        raise HTTPException(409, "Workstation challenge unavailable or used")
    try:
        signature = base64.b64decode(payload.signature_base64, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise HTTPException(422, "Malformed proof signature") from exc

    now = datetime.now(timezone.utc)
    challenge = WacomWorkstationChallenge(
        id=row.id,
        workstation_id=enrollment.workstation_id,
        session_id=row.session_id,
        nonce=base64.urlsafe_b64encode(bytes(row.nonce)).decode("ascii").rstrip("="),
        issued_at=_aware(row.created_at),
        expires_at=_aware(row.expires_at),
    )
    try:
        verify_enrolled_wacom_workstation_proof(
            challenge=challenge,
            expected_workstation_id=payload.workstation_id,
            expected_session_id=session_id,
            enrolled_public_key=bytes(enrollment.ed25519_public_key),
            signature=signature,
            now=now,
            consume_challenge_once=lambda challenge_id: consume_verified_wacom_challenge(
                db,
                challenge_id=challenge_id,
                company_id=context.company_id,
                enrollment_id=enrollment.id,
                session_id=session_id,
                now=now,
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "workstation_authenticated": True,
        "session_id": str(session_id),
        "workstation_id": str(payload.workstation_id),
        "capture_enabled": False,
        "preview_ticket_issued": False,
        "contract_signed": False,
    }
