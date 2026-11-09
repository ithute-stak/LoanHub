"""Domain-separated Wacom execution ceremony workstation-key proof.

Proves possession of an APPROVED workstation's key for one bounded request.
It does NOT prove that physical STU-540 handwriting was captured, that a
borrower consented or that the contract was executed.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
from datetime import datetime, timezone

from fastapi import HTTPException

from services.wacom_bridge_device_proof import verify_device_proof

PREFIX = "LOANHUB-WACOM-CEREMONY-WORKSTATION-V1"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{64}$")


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def ceremony_proof_message(*, challenge, challenge_secret: str, operator_id) -> bytes:
    """Canonical bound Ed25519 message. The plaintext is never persisted."""
    if not isinstance(challenge_secret, str) or not _TOKEN.fullmatch(challenge_secret):
        raise HTTPException(422, "Malformed ceremony challenge secret")
    if not hmac.compare_digest(
        hashlib.sha256(challenge_secret.encode("ascii")).hexdigest(),
        challenge.challenge_sha256,
    ):
        raise HTTPException(403, "Ceremony challenge mismatch")
    expiration = _utc(challenge.expires_at)
    if expiration is None:
        raise HTTPException(409, "Invalid ceremony challenge clock")
    return (
        f"{PREFIX}\n{challenge.company_id}\n{challenge.borrower_id}\n"
        f"{challenge.contract_id}\n{challenge.intent_id}\n"
        f"{challenge.authorization_id}\n{challenge.receipt_id}\n"
        f"{challenge.workstation_id}\n{operator_id}\n{challenge.id}\n"
        f"{challenge.candidate_sha256}\n{challenge.field_binding_sha256}\n"
        f"{challenge.challenge_sha256}\n{int(expiration.timestamp())}\n"
    ).encode("ascii")


def verify_ceremony_workstation_proof(
    *, challenge, challenge_secret: str, operator_id, enrollment, signature: bytes,
    now: datetime | None = None,
) -> bytes:
    now = _utc(now or datetime.now(timezone.utc))
    if now is None:
        raise HTTPException(409, "Invalid ceremony clock")
    expires = _utc(challenge.expires_at)
    requested = _utc(challenge.requested_at)
    if (challenge.status != "pending" or challenge.verified_at is not None
            or challenge.consumed_at is not None
            or expires is None or requested is None
            or not requested <= now < expires):
        raise HTTPException(409, "Ceremony challenge expired or already used")
    if (enrollment.company_id != challenge.company_id
            or enrollment.workstation_id != challenge.workstation_id
            or enrollment.status != "active"
            or enrollment.revoked_at is not None or enrollment.approved_at is None):
        raise HTTPException(403, "Unapproved or revoked Wacom workstation")
    message = ceremony_proof_message(
        challenge=challenge, challenge_secret=challenge_secret, operator_id=operator_id,
    )
    verify_device_proof(
        public_key=bytes(enrollment.ed25519_public_key),
        signature=signature, message=message,
    )
    return hashlib.sha256(message).digest()
