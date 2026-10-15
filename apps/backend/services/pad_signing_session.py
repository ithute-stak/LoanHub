"""State machine for future persisted loan-contract pad signing sessions.

These guards are pure and deliberately cannot mark a LoanContract signed.
Database persistence, verified signer identity, captured evidence and final PDF
approval must be wired before any customer-facing signing functionality.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID, uuid4

from fastapi import HTTPException

SESSION_TTL = timedelta(minutes=10)


class PadSessionState(str, Enum):
    CREATED = "created"
    CONSENTED = "consented"
    CAPTURED = "captured"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class PadSigningSession:
    id: UUID
    company_id: UUID
    contract_id: UUID
    contract_hash: str
    operator_id: UUID
    created_at: datetime
    expires_at: datetime
    state: PadSessionState = PadSessionState.CREATED
    consented_at: datetime | None = None
    evidence_sha256: str | None = None


def new_session(*, company_id: UUID, contract_id: UUID, contract_hash: str,
                operator_id: UUID, now: datetime | None = None) -> PadSigningSession:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware UTC time required")
    if len(contract_hash) != 64 or any(char not in "0123456789abcdef" for char in contract_hash):
        raise HTTPException(status_code=422, detail="Invalid contract hash")
    return PadSigningSession(
        id=uuid4(), company_id=company_id, contract_id=contract_id,
        contract_hash=contract_hash, operator_id=operator_id,
        created_at=now, expires_at=now + SESSION_TTL,
    )


def advance_session(session: PadSigningSession, *, action: str,
                    company_id: UUID, contract_id: UUID, contract_hash: str,
                    operator_id: UUID, now: datetime,
                    identity_verified: bool = False,
                    explicit_consent: bool = False,
                    evidence_sha256: str | None = None) -> PadSigningSession:
    """Validate transitions under a database lock once sessions are persisted."""
    if now.tzinfo is None:
        raise ValueError("Timezone-aware UTC time required")
    if (session.company_id != company_id or session.contract_id != contract_id
            or session.contract_hash != contract_hash or session.operator_id != operator_id):
        raise HTTPException(status_code=403, detail="Signing session identity mismatch")
    if session.state in {PadSessionState.COMPLETED, PadSessionState.CANCELLED, PadSessionState.EXPIRED}:
        raise HTTPException(status_code=409, detail="Signing session is closed")
    if now >= session.expires_at:
        return replace(session, state=PadSessionState.EXPIRED)
    if action == "cancel":
        return replace(session, state=PadSessionState.CANCELLED)
    if action == "consent" and session.state == PadSessionState.CREATED:
        if not identity_verified or not explicit_consent:
            raise HTTPException(status_code=409, detail="Signer verification and consent required")
        return replace(session, state=PadSessionState.CONSENTED, consented_at=now)
    if action == "capture" and session.state == PadSessionState.CONSENTED:
        if not evidence_sha256 or len(evidence_sha256) != 64 or any(c not in "0123456789abcdef" for c in evidence_sha256):
            raise HTTPException(status_code=422, detail="Invalid evidence checksum")
        return replace(session, state=PadSessionState.CAPTURED, evidence_sha256=evidence_sha256)
    # Completing a signing session requires separate immutable evidence storage,
    # document authorization and verified PDF generation, not this state machine.
    raise HTTPException(status_code=409, detail="Invalid or unsupported signing transition")
