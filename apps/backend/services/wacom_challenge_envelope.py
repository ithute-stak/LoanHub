"""Backend-authenticated envelope for local Wacom workstation proof requests.

An arbitrary web origin must not be able to turn the localhost connector
into a general-purpose Ed25519 signing oracle. The workstation verifies
this dedicated domain-separated authorization before it signs anything.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_DOMAIN = "LOANHUB-WACOM-CHALLENGE-ENVELOPE-V1"


def challenge_envelope_message(
    *, challenge_id: UUID, workstation_id: UUID, session_id: UUID,
    nonce: str, expires_at: datetime,
) -> bytes:
    if expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise ValueError("timezone-aware challenge expiry required")
    if not isinstance(nonce, str) or len(nonce) != 43:
        raise ValueError("invalid challenge nonce")
    raw = base64.urlsafe_b64decode(nonce + "=")
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != nonce:
        raise ValueError("invalid challenge nonce")
    return (
        f"{_DOMAIN}\n{challenge_id}\n{workstation_id}\n"
        f"{session_id}\n{nonce}\n{int(expires_at.timestamp())}\n"
    ).encode("ascii")


def sign_challenge_envelope(
    *, signer: Ed25519PrivateKey, key_id: str,
    challenge_id: UUID, workstation_id: UUID, session_id: UUID,
    nonce: str, expires_at: datetime,
) -> dict:
    if not isinstance(signer, Ed25519PrivateKey) or not key_id or len(key_id) > 64:
        raise ValueError("invalid backend challenge signer")
    message = challenge_envelope_message(
        challenge_id=challenge_id, workstation_id=workstation_id,
        session_id=session_id, nonce=nonce, expires_at=expires_at,
    )
    return {
        "backend_signature_base64": base64.b64encode(signer.sign(message)).decode("ascii"),
        "backend_signing_kid": key_id,
    }
