"""Internal verification of official S3 Object Lock PDF versions.

This service is NOT routed or publicly accessible. A QR/public_id only locates
an issuance, it is not proof or an authorization token. The authenticated
tenant and restricted database session must be supplied by trusted backend
authorization, never by browser-controlled company headers.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from database.models.document_issuance import DocumentIssuance
from services.document_issuance_database_readiness import require_document_issuance_database_ready
from services.document_issuance_immutable_binding import verify_locked_pdf_for_issuance
from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore
from services.document_issuance_integrity import (
    IssuanceFingerprint, verify_exact_document,
)
from services.object_storage_service import StorageUnavailableError


def verify_immutable_issuance(
    *, db: Session, authenticated_tenant_id: UUID, public_id: str,
    store: S3ObjectLockPdfStore, submitted_pdf: bytes | None = None,
) -> str:
    """Compare exact stored VersionId and optional submitted PDF without leakage.

    Returns 'issued_file_available_not_compared' for a valid canonical object
    when no PDF was supplied; only a byte-for-byte matching submitted PDF
    can return 'verified'. Failed storage/metadata reads never verify.
    """
    if not isinstance(authenticated_tenant_id, UUID):
        raise PermissionError("Authenticated tenant UUID required")
    if (not isinstance(public_id, str) or not (12 <= len(public_id) <= 96)
            or not all(c.isascii() and (c.isalnum() or c in "-_") for c in public_id)):
        raise ValueError("Invalid document locator")
    if not isinstance(store, S3ObjectLockPdfStore):
        raise PermissionError("S3 Object Lock store required")
    require_document_issuance_database_ready(db)
    record = db.query(DocumentIssuance).filter(
        DocumentIssuance.company_id == authenticated_tenant_id,
        DocumentIssuance.public_id == public_id,
    ).one_or_none()
    if record is None:
        return "not_found"
    if record.company_id != authenticated_tenant_id:
        # Defense in depth even when SQL is misconfigured.
        return "not_found"
    if record.status in {"revoked", "superseded"}:
        return record.status
    if record.status != "issued":
        return "unverified"
    try:
        canonical_pdf = verify_locked_pdf_for_issuance(
            issuance=record, tenant_id=authenticated_tenant_id, store=store,
        )
    except (StorageUnavailableError, OSError, ValueError, PermissionError):
        return "unavailable"
    if submitted_pdf is None:
        return "issued_file_available_not_compared"
    expected = IssuanceFingerprint(
        tenant_id=authenticated_tenant_id,
        public_id=public_id,
        sha256_hex=record.final_pdf_sha256,
        status=record.status,
    )
    try:
        return verify_exact_document(
            pdf=submitted_pdf, record=expected,
            expected_tenant_id=authenticated_tenant_id,
            requested_public_id=public_id,
        )
    except ValueError:
        return "altered"
