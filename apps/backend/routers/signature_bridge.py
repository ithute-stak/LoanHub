"""Strict staging-only import of offline signature captures.

No form insertion, signing, image retrieval or phone-based access is provided.
An operator must be authenticated within an active tenant. All imports are
quarantined for a future separately verified identity/consent workflow.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import LENDING_ROLES, COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.session import get_db
from database.models.signature_bridge import SignatureBridgeImport, SignatureBridgePhoneAlias
from services.signature_bridge_matching import normalized_phone_aliases

router = APIRouter(prefix="/signature-bridge", tags=["Signature Bridge (staging only)"])

class SignatureImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_record_id: UUID
    signer_kind: str = Field(pattern="^(client|officer)$")
    verified_signer_id: UUID
    consent_reference: str = Field(min_length=4, max_length=180)
    phone_numbers: str | None = Field(default=None, max_length=180)
    capture_base64: str = Field(min_length=4, max_length=175000)
    capture_sha256: str = Field(pattern="^[a-f0-9]{64}$")

def _fernet() -> Fernet:
    encoded = os.getenv("LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY", "")
    try:
        return Fernet(encoded.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Signature Bridge vault key not configured") from exc

def _enabled() -> None:
    # No production enablement until a reviewed production policy exists.
    if os.getenv("ENVIRONMENT", "").lower() != "staging" or os.getenv("LOANHUB_SIGNATURE_BRIDGE_IMPORT_ENABLED") != "true":
        raise HTTPException(503, "Signature Bridge import disabled")

@router.post("/imports", status_code=202)
def import_signature(
    body: SignatureImportRequest,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    _enabled()
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES)
    if context.company_id is None:
        raise HTTPException(403, "Tenant company required")
    if body.signer_kind == "officer" and body.verified_signer_id != context.user.id:
        raise HTTPException(403, "Officer capture must belong to authenticated operator")
    if body.signer_kind == "client" and not body.phone_numbers:
        raise HTTPException(422, "Client aliases are required for provisional import")
    if body.signer_kind == "officer" and body.phone_numbers:
        raise HTTPException(422, "Officer matching uses login identity, not phone number")
    try:
        raw = base64.b64decode(body.capture_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(422, "Invalid capture payload") from exc
    if not 1 <= len(raw) <= 128_000:
        raise HTTPException(413, "Capture payload exceeds 128KB")
    digest = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(digest, body.capture_sha256):
        raise HTTPException(422, "Capture digest mismatch")
    try:
        aliases = normalized_phone_aliases(body.phone_numbers) if body.phone_numbers else ()
    except ValueError as exc:
        raise HTTPException(422, "Invalid client phone aliases") from exc
    vault = _fernet()
    cipher = vault.encrypt(raw)
    # Tenant-scoped keyed digest avoids offline guessing of stored phone numbers.
    digest_key = base64.urlsafe_b64decode(os.environ["LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY"])
    alias_hash = hmac.new(
        digest_key, (str(context.company_id) + "|" + "|".join(aliases)).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest() if aliases else None
    existing = db.query(SignatureBridgeImport).filter(
        SignatureBridgeImport.company_id == context.company_id,
        SignatureBridgeImport.source_record_id == body.source_record_id,
    ).one_or_none()
    if existing is not None:
        if existing.payload_sha256 != digest or existing.signer_id != body.verified_signer_id or existing.signer_kind != body.signer_kind or existing.consent_reference != body.consent_reference or existing.phone_aliases_digest != alias_hash:
            raise HTTPException(409, "Conflicting retry for existing source record")
        return {"status":"pending_identity_review","source_record_id":str(body.source_record_id),"duplicate":True,"usable_for_signing":False}
    row = SignatureBridgeImport(
        company_id=context.company_id, source_record_id=body.source_record_id,
        signer_kind=body.signer_kind, signer_id=body.verified_signer_id,
        uploaded_by_user_id=context.user.id, payload_ciphertext=cipher,
        payload_sha256=digest, consent_reference=body.consent_reference,
        phone_aliases_digest=alias_hash, status="pending_identity_review",
    )
    try:
        db.add(row)
        db.flush()
        for phone in aliases:
            phone_digest = hmac.new(
                digest_key, (str(context.company_id) + "|" + phone).encode("ascii"),
                hashlib.sha256,
            ).hexdigest()
            db.add(SignatureBridgePhoneAlias(
                company_id=context.company_id,
                import_id=row.id,
                phone_digest=phone_digest,
            ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Concurrent import detected; retry with same record ID") from exc
    return {"status":"pending_identity_review","source_record_id":str(body.source_record_id),"duplicate":False,"usable_for_signing":False}

class ClientLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phones: str = Field(min_length=8, max_length=180)

@router.post("/resolve-client")
def resolve_client(
    body: ClientLookupRequest,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Return advisory record counts only, never signature bytes or signing rights."""
    response.headers["Cache-Control"] = "no-store"
    _enabled()
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES)
    if context.company_id is None:
        raise HTTPException(403, "Tenant company required")
    try:
        phones = normalized_phone_aliases(body.phones)
    except ValueError as exc:
        raise HTTPException(422, "Invalid client phone aliases") from exc
    _fernet()
    digest_key = base64.urlsafe_b64decode(os.environ["LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY"])
    digests = [
        hmac.new(digest_key, (str(context.company_id) + "|" + phone).encode("ascii"),
                 hashlib.sha256).hexdigest()
        for phone in phones
    ]
    rows = db.query(SignatureBridgeImport.id, SignatureBridgeImport.signer_id).join(
        SignatureBridgePhoneAlias, SignatureBridgePhoneAlias.import_id == SignatureBridgeImport.id
    ).filter(
        SignatureBridgeImport.company_id == context.company_id,
        SignatureBridgeImport.signer_kind == "client",
        SignatureBridgeImport.status == "pending_identity_review",
        SignatureBridgePhoneAlias.company_id == context.company_id,
        SignatureBridgePhoneAlias.phone_digest.in_(digests),
    ).distinct().all()
    sig_ids = {row[0] for row in rows}
    signers = {row[1] for row in rows}
    status = "not_found" if not sig_ids else "conflict" if len(sig_ids) > 1 or len(signers) > 1 else "pending_identity_review"
    return {
        "status": status,
        "match_count": len(sig_ids),
        "auto_apply": False,
        "requires_document_consent": True,
        "signature_available_for_form": False,
    }
