"""Verify enrolled Wacom workstation Ed25519 possession for preview requests.

Pure service. Backend callers must load an unexpired *server-issued* challenge,
the tenant-scoped enrollment record and live pad session from trusted storage.
No endpoint, enrollment approval, or signature capture is activated here.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException

_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_PREFIX = "LOANHUB-WACOM-WORKSTATION-POP-V1"
_MAX_CHALLENGE_LIFETIME = timedelta(seconds=30)


@dataclass(frozen=True)
class WacomWorkstationChallenge:
    id: UUID
    workstation_id: UUID
    session_id: UUID
    nonce: str  # 32 random bytes, unpadded URL-safe base64
    issued_at: datetime
    expires_at: datetime


def challenge_message(challenge: WacomWorkstationChallenge) -> bytes:
    return (
        f"{_PREFIX}\n{challenge.workstation_id}\n"
        f"{challenge.session_id}\n{challenge.nonce}\n"
        f"{int(challenge.expires_at.timestamp())}\n"
    ).encode("ascii")


def verify_enrolled_wacom_workstation_proof(
    *,
    challenge: WacomWorkstationChallenge,
    expected_workstation_id: UUID,
    expected_session_id: UUID,
    enrolled_public_key: bytes,
    signature: bytes,
    now: datetime,
    consume_challenge_once: Callable[[UUID], bool],
) -> None:
    """Fail closed if workstation identity or single-use proof is invalid.

    The consume callback MUST be a durable, atomic database operation that
    succeeds for exactly one use; do not substitute an in-memory set.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise HTTPException(409, "Workstation verification clock unavailable")
    if (challenge.workstation_id != expected_workstation_id or
            challenge.session_id != expected_session_id):
        raise HTTPException(403, "Workstation challenge scope mismatch")
    if (challenge.issued_at.tzinfo is None or
            challenge.expires_at.tzinfo is None or
            challenge.issued_at.utcoffset() is None or
            challenge.expires_at.utcoffset() is None or
            challenge.expires_at <= challenge.issued_at or
            challenge.expires_at - challenge.issued_at > _MAX_CHALLENGE_LIFETIME or
            now < challenge.issued_at or now >= challenge.expires_at):
        raise HTTPException(409, "Workstation challenge expired or invalid")
    if (not _NONCE_RE.fullmatch(challenge.nonce) or
            len(base64.urlsafe_b64decode(challenge.nonce + "=")) != 32):
        raise HTTPException(422, "Invalid workstation challenge nonce")
    if not isinstance(enrolled_public_key, bytes) or len(enrolled_public_key) != 32:
        raise HTTPException(403, "Enrolled workstation public key unavailable")
    if not isinstance(signature, bytes) or len(signature) != 64:
        raise HTTPException(403, "Invalid workstation signature")
    try:
        Ed25519PublicKey.from_public_bytes(enrolled_public_key).verify(
            signature, challenge_message(challenge)
        )
    except (InvalidSignature, ValueError) as exc:
        raise HTTPException(403, "Invalid workstation proof") from exc
    try:
        used = consume_challenge_once(challenge.id)
    except Exception as exc:
        raise HTTPException(503, "Workstation replay protection unavailable") from exc
    if used is not True:
        raise HTTPException(409, "Workstation challenge already used")
