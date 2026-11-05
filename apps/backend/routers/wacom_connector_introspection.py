"""Read-only Wacom connector preview introspection.

This endpoint is deliberately disabled unless a trusted ingress verifies
mTLS and injects workstation identity into request.scope. Headers, cookies,
and JSON identifiers are NEVER accepted as workstation authentication.
No evidence, signature or raw pen data is received.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
from datetime import datetime, timezone
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database.models.origination import LoanContract
from database.models.pad_signing import ContractPadSigningSession
from database.models.wacom_workstation import WacomWorkstationEnrollment
from database.session import get_db
from services.wacom_session_revalidation import current_pad_preview_eligibility

router = APIRouter(prefix="/wacom/connector", tags=["Wacom connector read-only"])
_AUD = "loanhub-wacom-connector-preview-v1"
_PURPOSE = "test-preview-only"
_HASH_CHARS = set("0123456789abcdef")


class ConnectorPreviewQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_ticket: str = Field(min_length=64, max_length=3500)


def _rejected() -> HTTPException:
    return HTTPException(403, "Wacom preview session unavailable")


def _read_ticket(token: str) -> dict:
    """Verify against a separately configured pinned backend public key."""
    key_b64 = os.getenv("LOANHUB_WACOM_PREVIEW_VERIFY_KEY_B64", "")
    try:
        key = base64.b64decode(key_b64, validate=True)
        if len(key) != 32 or base64.b64encode(key).decode() != key_b64:
            raise ValueError("invalid key")
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("segments")
        def decode(value: str) -> bytes:
            if not value or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for ch in value):
                raise ValueError("noncanonical token")
            raw = base64.urlsafe_b64decode(value + "=" * ((-len(value)) % 4))
            if base64.urlsafe_b64encode(raw).decode().rstrip("=") != value:
                raise ValueError("noncanonical base64")
            return raw
        header_bytes, claims_bytes, sig = map(decode, parts)
        if len(header_bytes) > 512 or len(claims_bytes) > 4096 or len(sig) != 64:
            raise ValueError("size")
        header = json.loads(header_bytes)
        if header != {"alg": "EdDSA", "kid": os.getenv("LOANHUB_WACOM_PREVIEW_SIGNING_KID"), "typ": "WACOM-PREVIEW"}:
            raise ValueError("wrong key")
        Ed25519PublicKey.from_public_bytes(key).verify(sig, (parts[0] + "." + parts[1]).encode("ascii"))
        claims = json.loads(claims_bytes)
        now = int(datetime.now(timezone.utc).timestamp())
        if (claims.get("aud") != _AUD or claims.get("purpose") != _PURPOSE
                or type(claims.get("iat")) is not int or type(claims.get("exp")) is not int
                or claims["iat"] > now or claims["exp"] <= now
                or not 0 < claims["exp"] - claims["iat"] <= 60
                or not isinstance(claims.get("jti"), str)
                or not 20 <= len(claims["jti"]) <= 128):
            raise ValueError("expired or wrong audience")
        return claims
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError, Exception) as error:
        raise _rejected() from error


def _uuid(claims: dict, name: str) -> UUID:
    try:
        value = claims[name]
        result = UUID(value)
        if str(result) != value:
            raise ValueError("noncanonical uuid")
        return result
    except (ValueError, TypeError, KeyError) as error:
        raise _rejected() from error


@router.post("/preview-introspect")
def introspect_wacom_preview(
    body: ConnectorPreviewQuery,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if os.getenv("LOANHUB_WACOM_CONNECTOR_INTROSPECTION_ENABLED") != "true":
        raise HTTPException(503, "Wacom connector introspection disabled")
    # Verified mTLS identity must be populated *only* by server-controlled
    # ASGI middleware from its trusted ingress, never X-Forwarded-* headers.
    verified = request.scope.get("verified_wacom_client_workstation_id")
    if not isinstance(verified, UUID):
        raise _rejected()
    claims = _read_ticket(body.preview_ticket)
    company_id = _uuid(claims, "company_id")
    operator_id = _uuid(claims, "operator_id")
    contract_id = _uuid(claims, "contract_id")
    session_id = _uuid(claims, "session_id")
    workstation_id = _uuid(claims, "workstation_id")
    contract_hash = claims.get("contract_hash")
    if (workstation_id != verified or not isinstance(contract_hash, str) or
            len(contract_hash) != 64 or set(contract_hash) - _HASH_CHARS):
        raise _rejected()
    enrolled = db.query(WacomWorkstationEnrollment).filter(
        WacomWorkstationEnrollment.company_id == company_id,
        WacomWorkstationEnrollment.workstation_id == verified,
        WacomWorkstationEnrollment.operator_user_id == operator_id,
        WacomWorkstationEnrollment.status == "active",
        WacomWorkstationEnrollment.approved_at.isnot(None),
        WacomWorkstationEnrollment.revoked_at.is_(None),
    ).one_or_none()
    if enrolled is None:
        raise _rejected()
    session = db.query(ContractPadSigningSession).filter(
        ContractPadSigningSession.id == session_id,
        ContractPadSigningSession.company_id == company_id,
        ContractPadSigningSession.operator_user_id == operator_id,
        ContractPadSigningSession.contract_id == contract_id,
        ContractPadSigningSession.contract_hash == contract_hash,
    ).one_or_none()
    contract = db.query(LoanContract).filter(
        LoanContract.id == contract_id,
        LoanContract.company_id == company_id,
        LoanContract.contract_hash == contract_hash,
    ).one_or_none()
    if session is None or contract is None:
        raise _rejected()
    if not current_pad_preview_eligibility(session, contract, datetime.now(timezone.utc))["preview_eligible"]:
        raise _rejected()
    # Field selection is backend-defined. Never use a browser-supplied ID
    # to authorize other signers or arbitrary document inputs.
    return {
        "company_id": str(company_id),
        "operator_id": str(operator_id),
        "contract_id": str(contract_id),
        "contract_hash": contract_hash,
        "session_id": str(session_id),
        "workstation_id": str(workstation_id),
        "session_key": str(session_id),
        "field_id": "borrower_signature",
    }
