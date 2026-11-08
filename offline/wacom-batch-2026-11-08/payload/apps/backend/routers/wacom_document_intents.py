"""First-party Wacom document-specific signing evidence workflow.

Produces reviewed, immutable *evidence*, not a signed loan agreement. Actual
PDF signing is a separate explicit authorized and audited act.
"""
from __future__ import annotations

import os

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES, LENDING_ROLES, TenantContext,
    get_tenant_context, require_tenant_roles,
)
from database.models.company_client import CompanyBorrowerAccount
from database.models.origination import LoanContract
from database.models.file_management import ManagedFile
from database.models.wacom_bridge_session import WacomBridgeSession
from database.models.wacom_document_intent import WacomDocumentIntent
from database.session import get_db
from services.wacom_document_policy import (
    IntentIdentity, IntentStatus, consent_digest, require_transition, check_valid_until,
)
from services.wacom_bridge_sessions import authorize_bridge_session

def _feature_enabled() -> None:
    if os.getenv("LOANHUB_WACOM_DOCUMENT_INTENTS_ENABLED", "") != "1":
        raise HTTPException(503, "Document-intent workflow is not enabled")


router = APIRouter(prefix="/wacom-document-intents", tags=["Wacom Per-Document Consent Evidence"],
                   dependencies=[Depends(_feature_enabled)])


class PrepareDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    borrower_id: UUID
    contract_id: UUID
    source_file_id: UUID
    workstation_id: UUID
    document_version: str = Field(min_length=1, max_length=80)


class ConfirmDocumentConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signer_confirmation: str = Field(min_length=1, max_length=100)
    consent_reference: str = Field(min_length=4, max_length=180)
    displayed_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AttachEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_file_id: UUID


class ReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(pattern=r"^(verify|reject)$")
    identity_checked: bool
    consent_checked: bool
    reference: str = Field(min_length=4, max_length=180)
    reason: str = Field(min_length=8, max_length=400)


def _session_device(db: Session, ctx: TenantContext, token: str | None) -> UUID:
    require_tenant_roles(ctx, LENDING_ROLES)
    authorize_bridge_session(db, context=ctx, token=token)
    # Scope has already been checked by authorize_bridge_session; digest is
    # re-read to determine the PC that was proved by Ed25519.
    import hashlib
    digest = hashlib.sha256(token.encode("ascii")).digest()
    row = db.query(WacomBridgeSession).filter(
        WacomBridgeSession.company_id == ctx.company_id,
        WacomBridgeSession.employee_user_id == ctx.user.id,
        WacomBridgeSession.token_sha256 == digest,
        WacomBridgeSession.revoked_at.is_(None),
        WacomBridgeSession.expires_at > datetime.now(timezone.utc),
    ).one_or_none()
    if row is None:
        raise HTTPException(403, "Workstation session unavailable")
    return row.workstation_id


def _current_intent(db: Session, ctx: TenantContext, intent_id: UUID, *, lock=True):
    q = db.query(WacomDocumentIntent).filter(
        WacomDocumentIntent.id == intent_id,
        WacomDocumentIntent.company_id == ctx.company_id,
    )
    row = (q.with_for_update() if lock else q).one_or_none()
    if row is None:
        raise HTTPException(404, "Document intent unavailable")
    return row


def _response(row: WacomDocumentIntent) -> dict:
    return {
        "intent_id": str(row.id),
        "status": row.status,
        "company_id": str(row.company_id),
        "contract_id": str(row.contract_id),
        "borrower_id": str(row.borrower_id),
        "document_sha256": row.document_sha256,
        "document_version": row.document_version,
        "binding_sha256": row.binding_sha256,
        "consent_reference": row.consent_reference,
        "expires_at": row.expires_at,
        "signing_authorized": False,
        "signed_contract_created": False,
        "signature_reuse_allowed": False,
    }


@router.post("", status_code=201)
def prepare_intent(
    body: PrepareDocument, response: Response,
    x_wacom_bridge_session: str | None = Header(default=None, alias="X-Wacom-Bridge-Session"),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    workstation_id = _session_device(db, ctx, x_wacom_bridge_session)
    if body.workstation_id != workstation_id:
        raise HTTPException(403, "Workstation does not match authenticated PC")
    client = db.query(CompanyBorrowerAccount).filter(
        CompanyBorrowerAccount.company_id == ctx.company_id,
        CompanyBorrowerAccount.borrower_id == body.borrower_id,
    ).one_or_none()
    if client is None or (ctx.staff.role not in COMPANY_MANAGEMENT_ROLES and
                          (ctx.branch_id is None or client.branch_id != ctx.branch_id)):
        raise HTTPException(404, "Client not available in active company branch")
    contract = db.query(LoanContract).filter(
        LoanContract.id == body.contract_id,
        LoanContract.company_id == ctx.company_id,
        LoanContract.borrower_id == body.borrower_id,
        LoanContract.pdf_file_id == body.source_file_id,
    ).one_or_none()
    if contract is None or contract.loan is None:
        raise HTTPException(404, "Contract and PDF do not belong to this borrower and company")
    if ctx.staff.role not in COMPANY_MANAGEMENT_ROLES and contract.loan.branch_id != ctx.branch_id:
        raise HTTPException(403, "Contract belongs to another company branch")
    if body.document_version != str(contract.version):
        raise HTTPException(409, "Stale contract version; new consent required")
    if contract.borrower_signed_at is not None or contract.locked_at is not None:
        raise HTTPException(409, "Contract already signed or locked")
    # File content's digest must be the server-stored digest from an encrypted,
    # clean company-owned exact contract document, not a caller-provided hash.
    source = db.query(ManagedFile).filter(
        ManagedFile.id == body.source_file_id,
        ManagedFile.company_id == ctx.company_id,
        ManagedFile.mime_type == "application/pdf",
        ManagedFile.is_encrypted.is_(True),
        ManagedFile.is_deleted.is_(False),
        ManagedFile.scan_status == "clean",
    ).one_or_none()
    if source is None or not re.fullmatch(r"[0-9a-f]{64}", source.checksum_sha256 or ""):
        raise HTTPException(409, "Verified immutable contract PDF not available")
    identity = IntentIdentity(
        company_id=ctx.company_id, borrower_id=body.borrower_id,
        contract_id=body.contract_id, source_file_id=body.source_file_id, operator_user_id=ctx.user.id,
        workstation_id=workstation_id, document_sha256=source.checksum_sha256,
        document_version=body.document_version,
    )
    existing = db.query(WacomDocumentIntent.id).filter(
        WacomDocumentIntent.company_id == ctx.company_id,
        WacomDocumentIntent.borrower_id == body.borrower_id,
        WacomDocumentIntent.contract_id == body.contract_id,
        WacomDocumentIntent.document_sha256 == identity.document_sha256,
    ).first()
    if existing:
        raise HTTPException(409, "Exact document already has a signing-evidence intent")
    row = WacomDocumentIntent(
        id=uuid4(), company_id=ctx.company_id, borrower_id=body.borrower_id,
        contract_id=body.contract_id, source_file_id=body.source_file_id, operator_user_id=ctx.user.id,
        workstation_id=workstation_id, document_sha256=identity.document_sha256,
        document_version=identity.document_version,
        binding_sha256=identity.binding_sha256(), status=IntentStatus.PREPARED,
        expires_at=datetime.now(timezone.utc)+timedelta(minutes=10),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Exact-document signing intent already exists") from exc
    return _response(row)


@router.post("/{intent_id}/consent")
def record_consent(
    intent_id: UUID, body: ConfirmDocumentConsent, response: Response,
    x_wacom_bridge_session: str | None = Header(default=None, alias="X-Wacom-Bridge-Session"),
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    pc = _session_device(db, ctx, x_wacom_bridge_session)
    row = _current_intent(db, ctx, intent_id)
    if row.operator_user_id != ctx.user.id or row.workstation_id != pc:
        raise HTTPException(403, "Different authenticated operator or workstation")
    try:
        require_transition(row.status, IntentStatus.CONSENTED)
        check_valid_until(row.expires_at)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if body.displayed_document_sha256 != row.document_sha256:
        raise HTTPException(409, "Document has changed; new consent required")
    current_contract = db.query(LoanContract).filter(
        LoanContract.id == row.contract_id,
        LoanContract.company_id == ctx.company_id,
        LoanContract.borrower_id == row.borrower_id,
        LoanContract.pdf_file_id == row.source_file_id,
        LoanContract.version == int(row.document_version),
        LoanContract.locked_at.is_(None),
        LoanContract.borrower_signed_at.is_(None),
    ).one_or_none()
    if current_contract is None:
        raise HTTPException(409, "Contract changed or is no longer available for signing")
    current_pdf = db.query(ManagedFile).filter(
        ManagedFile.id == row.source_file_id,
        ManagedFile.company_id == ctx.company_id,
        ManagedFile.mime_type == "application/pdf",
        ManagedFile.is_encrypted.is_(True),
        ManagedFile.is_deleted.is_(False),
        ManagedFile.scan_status == "clean",
    ).one_or_none()
    if current_pdf is None or current_pdf.checksum_sha256 != row.document_sha256:
        raise HTTPException(409, "Original PDF changed or became unavailable")
    # Local operator cannot assert the borrower's verified identity by code
    # alone; independent verification is still required downstream.
    try:
        commitment = consent_digest(row.binding_sha256,
                                    body.signer_confirmation, body.consent_reference)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    row.consent_reference = body.consent_reference
    row.consent_commitment_sha256 = commitment
    row.consent_at = datetime.now(timezone.utc)
    row.status = IntentStatus.CONSENTED
    db.commit()
    return _response(row)


@router.post("/{intent_id}/evidence")
def attach_evidence(
    intent_id: UUID, body: AttachEvidence, response: Response,
    x_wacom_bridge_session: str | None = Header(default=None, alias="X-Wacom-Bridge-Session"),
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    pc = _session_device(db, ctx, x_wacom_bridge_session)
    row = _current_intent(db, ctx, intent_id)
    if row.operator_user_id != ctx.user.id or row.workstation_id != pc:
        raise HTTPException(403, "Different authenticated operator or workstation")
    try:
        require_transition(row.status, IntentStatus.EVIDENCE_UPLOADED)
        check_valid_until(row.expires_at)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    evidence = db.query(ManagedFile).filter(
        ManagedFile.id == body.evidence_file_id,
        ManagedFile.company_id == ctx.company_id,
        ManagedFile.owner_user_id == ctx.user.id,
        ManagedFile.linked_entity_type == "wacom_client",
        ManagedFile.linked_entity_id == str(row.borrower_id),
        ManagedFile.category == "wacom_client_signature_pending",
        ManagedFile.is_encrypted.is_(True),
        ManagedFile.is_confidential.is_(True),
        ManagedFile.is_deleted.is_(False),
        ManagedFile.scan_status == "clean",
    ).one_or_none()
    if evidence is None:
        raise HTTPException(404, "Private pending capture evidence unavailable")
    # Prevent binding an old or generic saved handwriting image to a new PDF.
    expected_description = "Wacom capture pending identity and consent review; reference: " + row.consent_reference
    if evidence.description != expected_description or not row.consent_at:
        raise HTTPException(409, "Handwriting evidence consent does not match this document")
    captured_at = evidence.created_at
    if captured_at is None:
        raise HTTPException(409, "Missing handwriting capture timestamp")
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    consent_at = row.consent_at
    if consent_at.tzinfo is None:
        consent_at = consent_at.replace(tzinfo=timezone.utc)
    if captured_at < consent_at:
        raise HTTPException(409, "Previously captured handwriting cannot be reused for new consent")
    bound_elsewhere = db.query(WacomDocumentIntent.id).filter(
        WacomDocumentIntent.company_id == ctx.company_id,
        WacomDocumentIntent.evidence_file_id == evidence.id,
    ).first()
    if bound_elsewhere is not None:
        raise HTTPException(409, "Handwriting evidence already bound to another document")
    row.evidence_file_id = evidence.id
    row.evidence_sha256 = evidence.checksum_sha256
    row.status = IntentStatus.EVIDENCE_UPLOADED
    db.commit()
    return _response(row)


@router.post("/{intent_id}/review")
def review_intent(
    intent_id: UUID, body: ReviewEvidence, response: Response,
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)
    row = _current_intent(db, ctx, intent_id)
    if ctx.user.id == row.operator_user_id:
        raise HTTPException(403, "Independent reviewer required")
    if row.status != IntentStatus.EVIDENCE_UPLOADED:
        raise HTTPException(409, "Review requires attached evidence")
    evidence = db.query(ManagedFile).filter(
        ManagedFile.id == row.evidence_file_id,
        ManagedFile.company_id == ctx.company_id,
        ManagedFile.linked_entity_type == "wacom_client",
        ManagedFile.linked_entity_id == str(row.borrower_id),
        ManagedFile.category == "wacom_client_capture_verified",
        ManagedFile.is_encrypted.is_(True),
        ManagedFile.is_confidential.is_(True),
        ManagedFile.is_deleted.is_(False),
        ManagedFile.scan_status == "clean",
    ).one_or_none()
    if evidence is None or evidence.checksum_sha256 != row.evidence_sha256:
        raise HTTPException(409, "Independent capture review or evidence integrity missing")
    if body.decision == "verify" and not (body.identity_checked and body.consent_checked):
        raise HTTPException(422, "Identity and explicit document consent must be checked")
    # This is evidence verification only. It never writes to a signed PDF,
    # authorizes reusable signatures or changes loan/contract status.
    row.status = IntentStatus.VERIFIED if body.decision == "verify" else IntentStatus.REJECTED
    row.review_by = ctx.user.id
    row.review_at = datetime.now(timezone.utc)
    row.review_reference = body.reference
    row.review_reason = body.reason
    db.commit()
    return _response(row)


@router.get("/{intent_id}")
def read_intent(
    intent_id: UUID, response: Response,
    x_wacom_bridge_session: str | None = Header(default=None, alias="X-Wacom-Bridge-Session"),
    db: Session = Depends(get_db), ctx: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "no-store"
    pc = _session_device(db, ctx, x_wacom_bridge_session)
    row = _current_intent(db, ctx, intent_id, lock=False)
    if row.operator_user_id != ctx.user.id or row.workstation_id != pc:
        raise HTTPException(403, "Document evidence belongs to another operator")
    return _response(row)
