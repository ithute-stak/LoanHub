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
from database.models.person import Person
from database.models.borrower import Borrower
from database.models.company_client import CompanyBorrowerAccount
from database.models.borrower_signature import BorrowerSavedSignature
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
    def _existing_record():
        return db.query(SignatureBridgeImport).filter(
            SignatureBridgeImport.company_id == context.company_id,
            SignatureBridgeImport.source_record_id == body.source_record_id,
        ).one_or_none()

    def _duplicate_or_conflict(existing):
        if (existing.payload_sha256 != digest
                or existing.signer_id != body.verified_signer_id
                or existing.signer_kind != body.signer_kind
                or existing.consent_reference != body.consent_reference
                or existing.phone_aliases_digest != alias_hash):
            raise HTTPException(409, "Conflicting retry for existing source record")
        # The caller supplied a claimed identity, not an identity attestation.
        # No stored record is authorized for form use.
        return {
            "status": "pending_identity_review",
            "source_record_id": str(body.source_record_id),
            "company_id": str(context.company_id),
            "duplicate": True,
            "usable_for_signing": False,
        }

    existing = _existing_record()
    if existing is not None:
        return _duplicate_or_conflict(existing)
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
        # A concurrent writer may have committed an identical record while this
        # request was inserting. Re-read after rollback and acknowledge only if
        # all identity claims, consent references and digests are unchanged.
        race_winner = _existing_record()
        if race_winner is not None:
            return _duplicate_or_conflict(race_winner)
        raise HTTPException(409, "Import integrity conflict; record not acknowledged") from exc
    return {"status":"pending_identity_review","source_record_id":str(body.source_record_id),"company_id":str(context.company_id),"duplicate":False,"usable_for_signing":False}


class NationalIdLookupRequest(BaseModel):
    """Exact-match request, never unbounded National ID enumeration."""
    model_config = ConfigDict(extra="forbid")
    national_id: str = Field(min_length=4, max_length=50)


@router.post("/lookup-national-id")
def lookup_national_id(
    body: NationalIdLookupRequest,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Tenant-scoped exact National ID resolution and signature reuse status."""
    response.headers["Cache-Control"] = "no-store"
    _enabled()
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES)
    if context.company_id is None:
        raise HTTPException(403, "Tenant company required")
    national_id = body.national_id.strip()
    if not national_id or len(national_id) < 4 or any(ord(ch) < 32 for ch in national_id):
        raise HTTPException(422, "Invalid National ID")
    matches = db.query(Borrower.id, Person.first_name, Person.middle_name, Person.last_name).join(
        Person, Person.user_id == Borrower.user_id
    ).join(
        CompanyBorrowerAccount, CompanyBorrowerAccount.borrower_id == Borrower.id
    ).filter(
        CompanyBorrowerAccount.company_id == context.company_id,
        Person.national_id == national_id,
    ).limit(2).all()
    if not matches:
        return {"status": "not_found", "matches": [], "may_capture": False,
                "may_reuse": False, "may_sign_contract": False}
    if len(matches) != 1:
        return {"status": "conflict", "matches": [], "may_capture": False,
                "may_reuse": False, "may_sign_contract": False}
    borrower_id, first, middle, last = matches[0]
    saved = db.query(BorrowerSavedSignature.id).filter(
        BorrowerSavedSignature.company_id == context.company_id,
        BorrowerSavedSignature.borrower_id == borrower_id,
        BorrowerSavedSignature.status == "active",
    ).limit(2).all()
    pending = db.query(SignatureBridgeImport.id).filter(
        SignatureBridgeImport.company_id == context.company_id,
        SignatureBridgeImport.signer_kind == "client",
        SignatureBridgeImport.signer_id == borrower_id,
        SignatureBridgeImport.status == "pending_identity_review",
    ).limit(1).all()
    full_name = " ".join(part.strip() for part in (first, middle, last) if part and part.strip())
    if saved or pending:
        status = "existing_signature" if saved else "pending_signature_review"
    else:
        status = "matched_no_signature"
    return {
        "status": status,
        "matches": [{
            "borrower_id": str(borrower_id),
            "full_name": full_name,
            "national_id_suffix": national_id[-4:],
            "signature_state": (
                "active_saved" if saved else "pending_review" if pending else "none"
            ),
        }],
        "may_capture": False,
        "may_reuse": False,
        "may_sign_contract": False,
    }


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

@router.get("/resolve-officer")
def resolve_officer(
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """The authenticated LoanHub session is the sole source of officer identity."""
    response.headers["Cache-Control"] = "no-store"
    _enabled()
    require_tenant_roles(context, LENDING_ROLES | COMPANY_MANAGEMENT_ROLES)
    if context.company_id is None:
        raise HTTPException(403, "Tenant company required")
    rows = db.query(SignatureBridgeImport.id).filter(
        SignatureBridgeImport.company_id == context.company_id,
        SignatureBridgeImport.signer_kind == "officer",
        SignatureBridgeImport.signer_id == context.user.id,
        SignatureBridgeImport.status == "pending_identity_review",
    ).all()
    count = len({row[0] for row in rows})
    return {
        "status": "not_found" if count == 0 else "conflict" if count > 1 else "pending_identity_review",
        "match_count": count,
        "auto_apply": False,
        "requires_document_consent": True,
        "signature_available_for_form": False,
    }
