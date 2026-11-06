"""Local-PC Wacom API. No additional server-side bridge or capture daemon.

Uploads remain private, quarantined evidence until a separate verified
identity/consent workflow approves signing or reuse.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, LENDING_ROLES, TenantContext,
    get_tenant_context, require_tenant_roles,
)
from database.config.config import settings
from database.models.audit_log import AuditLog
from database.models.borrower import Borrower
from database.models.borrower_signature import BorrowerSavedSignature
from database.models.company_client import CompanyBorrowerAccount
from database.models.file_management import ManagedFile
from database.models.person import Person
from database.session import get_db
from services.file_service import store_bytes

router = APIRouter(prefix="/local-signatures", tags=["Local Wacom PC"])
_ALLOWED = LENDING_ROLES | COMPANY_MANAGEMENT_ROLES
_OPERATOR_CATEGORY = "wacom_operator_signature_pending"
_CLIENT_CATEGORY = "wacom_client_signature_pending"
_MAX_CAPTURE_BYTES = 128_000


class ClientLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    national_id: str = Field(min_length=4, max_length=50)


class CaptureSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signer_kind: str = Field(pattern="^(operator|client)$")
    borrower_id: UUID | None = None
    consent_reference: str = Field(min_length=4, max_length=180)
    capture_png_base64: str = Field(min_length=4, max_length=175000)
    capture_sha256: str = Field(pattern="^[0-9a-f]{64}$")


def _authorized(context: TenantContext) -> None:
    if context.company_id is None or context.staff is None:
        raise HTTPException(403, "Active company staff membership required")
    require_tenant_roles(context, _ALLOWED)


def _client_account(db: Session, context: TenantContext, borrower_id: UUID):
    query = db.query(CompanyBorrowerAccount).filter(
        CompanyBorrowerAccount.company_id == context.company_id,
        CompanyBorrowerAccount.borrower_id == borrower_id,
    )
    if context.staff.role not in COMPANY_MANAGEMENT_ROLES:
        if context.branch_id is None:
            raise HTTPException(403, "Active company branch required")
        query = query.filter(CompanyBorrowerAccount.branch_id == context.branch_id)
    account = query.one_or_none()
    if account is None:
        raise HTTPException(404, "Client unavailable")
    return account


def _pending_file(db: Session, context: TenantContext, *, category: str, kind: str, identity: UUID):
    return db.query(ManagedFile).filter(
        ManagedFile.company_id == context.company_id,
        ManagedFile.category == category,
        ManagedFile.linked_entity_type == kind,
        ManagedFile.linked_entity_id == str(identity),
        ManagedFile.is_deleted.is_(False),
    )



def _reserve_lookup_attempt(db: Session, context: TenantContext) -> None:
    """Serialize per-operator lookup budgets; log no National ID or person name."""
    lock_identity = f"local-wacom-lookup:{context.company_id}:{context.user.id}"
    key = int.from_bytes(hashlib.sha256(lock_identity.encode("ascii")).digest()[:8], "big", signed=True)
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        used = db.query(func.count(AuditLog.id)).filter(
            AuditLog.company_id == context.company_id,
            AuditLog.user_id == context.user.id,
            AuditLog.action == "local_signatures.client_lookup",
            AuditLog.created_at >= cutoff,
        ).scalar()
        if not isinstance(used, int):
            raise ValueError("Invalid lookup audit count")
        if used >= 8:
            db.rollback()
            raise HTTPException(429, "Client lookup rate limit reached")
        db.add(AuditLog(
            company_id=context.company_id,
            user_id=context.user.id,
            branch_id=context.branch_id,
            action="local_signatures.client_lookup",
            table_name="people",
            entity_type="privacy_access",
            status="attempted",
            description="Authenticated exact client identity lookup",
            event_data={"lookup_type": "national_id", "contains_personal_data": False},
        ))
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "Lookup audit unavailable") from exc


@router.get("/me/status")
def operator_signature_status(
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    _authorized(context)
    pending = _pending_file(
        db, context, category=_OPERATOR_CATEGORY,
        kind="wacom_operator", identity=context.user.id,
    ).first()
    person = context.user.person
    return {
        "operator_id": str(context.user.id),
        "full_name": person.full_name if person else None,
        "company_id": str(context.company_id),
        "signature_status": "pending_review" if pending else "missing",
        "requires_capture": pending is None,
        "usable_for_signing": False,
    }


@router.post("/clients/lookup")
def lookup_client(
    body: ClientLookup,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    _authorized(context)
    national_id = body.national_id.strip()
    if len(national_id) < 4 or any(ord(char) < 33 for char in national_id):
        raise HTTPException(422, "Invalid National ID")
    query = (
        db.query(CompanyBorrowerAccount.borrower_id, Person.first_name,
                 Person.middle_name, Person.last_name)
        .join(Borrower, Borrower.id == CompanyBorrowerAccount.borrower_id)
        .join(Person, Person.user_id == Borrower.user_id)
        .filter(
            CompanyBorrowerAccount.company_id == context.company_id,
            Person.national_id == national_id,
        )
    )
    if context.staff.role not in COMPANY_MANAGEMENT_ROLES:
        if context.branch_id is None:
            raise HTTPException(403, "Active company branch required")
        query = query.filter(CompanyBorrowerAccount.branch_id == context.branch_id)
    _reserve_lookup_attempt(db, context)
    matches = query.limit(2).all()
    if not matches:
        return {"status": "not_found", "client": None}
    if len(matches) != 1:
        return {"status": "conflict", "client": None}
    borrower_id, first, middle, last = matches[0]
    full_name = " ".join(n.strip() for n in (first, middle, last) if n and n.strip())
    if not full_name:
        return {"status": "conflict", "client": None}
    existing = db.query(BorrowerSavedSignature.id).filter(
        BorrowerSavedSignature.company_id == context.company_id,
        BorrowerSavedSignature.borrower_id == borrower_id,
        BorrowerSavedSignature.status == "active",
    ).first()
    pending = _pending_file(
        db, context, category=_CLIENT_CATEGORY,
        kind="wacom_client", identity=borrower_id,
    ).first()
    signature_status = "active" if existing else "pending_review" if pending else "missing"
    return {
        "status": "matched",
        "client": {
            "borrower_id": str(borrower_id),
            "full_name": full_name,
            "signature_status": signature_status,
            "requires_capture": signature_status == "missing",
        },
        "may_reuse": False,
        "may_sign_contract": False,
    }


@router.post("/captures", status_code=202)
def upload_capture(
    body: CaptureSubmission,
    response: Response,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    _authorized(context)
    if not settings.FILE_ENCRYPTION_ENABLED:
        raise HTTPException(503, "Encrypted signature storage required")
    if body.signer_kind == "operator":
        if body.borrower_id is not None:
            raise HTTPException(422, "Operator capture cannot specify borrower ID")
        identity = context.user.id
        category, kind = _OPERATOR_CATEGORY, "wacom_operator"
    else:
        if body.borrower_id is None:
            raise HTTPException(422, "Client borrower ID required")
        _client_account(db, context, body.borrower_id)
        identity = body.borrower_id
        category, kind = _CLIENT_CATEGORY, "wacom_client"

    try:
        raw = base64.b64decode(body.capture_png_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "Invalid signature encoding") from exc
    if not 1 <= len(raw) <= _MAX_CAPTURE_BYTES:
        raise HTTPException(413, "Signature capture size invalid")
    if not raw.startswith(bytes.fromhex("89504e470d0a1a0a")):
        raise HTTPException(422, "PNG signature capture required")
    digest = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(digest, body.capture_sha256):
        raise HTTPException(422, "Signature digest mismatch")

    # An identical retry is acknowledged rather than creating another file.
    existing = _pending_file(db, context, category=category, kind=kind, identity=identity).filter(
        ManagedFile.checksum_sha256 == digest,
    ).first()
    if existing is not None:
        return {"status": "pending_review", "file_id": str(existing.id),
                "duplicate": True, "usable_for_signing": False}

    record = store_bytes(
        db,
        content=raw,
        original_name="wacom-signature.png",
        mime_type="image/png",
        owner_user_id=context.user.id,
        company_id=context.company_id,
        branch_id=context.branch_id,
        category=category,
        visibility="private",
        description="Wacom capture pending identity and consent review; reference: " + body.consent_reference,
        linked_entity_type=kind,
        linked_entity_id=str(identity),
        is_confidential=True,
    )
    db.commit()
    return {"status": "pending_review", "file_id": str(record.id),
            "duplicate": False, "usable_for_signing": False}
