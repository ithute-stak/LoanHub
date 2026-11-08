"""Domain-separated Ed25519 proof for the first-party, multi-operator PC bridge.

A proof is bound to one LoanHub tenant, employee, workstation and short-lived
server challenge. This component verifies possession; it does not issue a
lending session or authorize any form of contract signing.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException

PREFIX = "LOANHUB-WACOM-BRIDGE-DEVICE-V1"
TTL = timedelta(seconds=30)


def proof_message(*, company_id: UUID, employee_id: UUID, workstation_id: UUID,
                  challenge_id: UUID, nonce: bytes, expires_at: datetime) -> bytes:
    if len(nonce) != 32 or expires_at.tzinfo is None or expires_at.utcoffset() is None:
        raise HTTPException(409, "Invalid workstation challenge")
    return (f"{PREFIX}\n{company_id}\n{employee_id}\n{workstation_id}\n"
            f"{challenge_id}\n{base64.urlsafe_b64encode(nonce).decode('ascii').rstrip('=')}\n"
            f"{int(expires_at.timestamp())}\n").encode("ascii")


def verify_device_proof(*, public_key: bytes, signature: bytes, message: bytes) -> None:
    if len(public_key) != 32 or len(signature) != 64:
        raise HTTPException(403, "Invalid workstation device proof")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except (InvalidSignature, ValueError) as exc:
        raise HTTPException(403, "Invalid workstation device proof") from exc
