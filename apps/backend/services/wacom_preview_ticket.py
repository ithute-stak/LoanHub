"""Offline Ed25519 ticket issuer for future Wacom *preview-only* sessions.

Pure service: NO HTTP endpoint, no capture stream, no signature finalization.
Caller must first check database-backed tenant/session authorization via
authorize_wacom_preview_admission. Private key must come from secured server
configuration; never bundle or transmit it to a workstation.
"""
from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.wacom_preview_admission import authorize_wacom_preview_admission

MAX_PREVIEW_TICKET_SECONDS = 60
PREVIEW_AUDIENCE = "loanhub-wacom-connector-preview-v1"
PREVIEW_PURPOSE = "test-preview-only"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def issue_wacom_preview_ticket(
    *,
    signing_key: Ed25519PrivateKey,
    key_id: str,
    session: object,
    authenticated_company_id: UUID,
    authenticated_operator_id: UUID,
    current_contract_id: UUID,
    current_contract_hash: str,
    expected_session_id: UUID,
    authorized_workstation_id: UUID,
    now: datetime,
    lifetime: timedelta = timedelta(seconds=30),
) -> str:
    """Only after independently validated, persisted preview-session context.

    The signed payload includes no name, ID number or biometric data.
    This is not consent, evidence, or permission to finalize a contract.
    A future connector MUST verify signature/key-id, exact authenticated
    workstation identity, clock bounds, scope, and single-use jti against
    a durable/atomic replay store before admitting any captured data.
    """
    authorize_wacom_preview_admission(
        session=session, authenticated_company_id=authenticated_company_id,
        authenticated_operator_id=authenticated_operator_id,
        current_contract_id=current_contract_id,
        current_contract_hash=current_contract_hash,
        expected_session_id=expected_session_id, now=now,
    )
    if not isinstance(signing_key, Ed25519PrivateKey):
        raise ValueError("Ed25519 signing key required")
    if not isinstance(key_id, str) or not (1 <= len(key_id) <= 64) or not all(
        c.isascii() and (c.isalnum() or c in "-_") for c in key_id
    ):
        raise ValueError("Trusted preview signing key identifier required")
    if not isinstance(authorized_workstation_id, UUID):
        raise ValueError("Authenticated workstation UUID required")
    if not timedelta(0) < lifetime <= timedelta(seconds=MAX_PREVIEW_TICKET_SECONDS):
        raise ValueError("Preview ticket must be bounded to 60 seconds")
    issued_at = int(now.astimezone(timezone.utc).timestamp())
    # Never let a ticket outlive its persisted signing session.
    remaining = int((session.expires_at - now).total_seconds())
    duration = min(int(lifetime.total_seconds()), remaining)
    if duration <= 0:
        raise ValueError("Signing session expires before ticket validity")

    header = {"alg": "EdDSA", "kid": key_id, "typ": "WACOM-PREVIEW"}
    payload = {
        "aud": PREVIEW_AUDIENCE,
        "purpose": PREVIEW_PURPOSE,
        "jti": secrets.token_urlsafe(24),
        "iat": issued_at,
        "exp": issued_at + duration,
        "company_id": str(authenticated_company_id),
        "operator_id": str(authenticated_operator_id),
        "contract_id": str(current_contract_id),
        "contract_hash": current_contract_hash,
        "session_id": str(expected_session_id),
        "workstation_id": str(authorized_workstation_id),
    }
    def segment(data: dict) -> str:
        return _b64url(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    body = f"{segment(header)}.{segment(payload)}"
    signature = signing_key.sign(body.encode("ascii"))
    return f"{body}.{_b64url(signature)}"
