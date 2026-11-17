"""Internal verification of an issued PDF and its protected stored copy.

A QR locator proves nothing by itself. This service requires an authenticated
tenant ID and authoritative DB lookup, and it never reveals borrower details.
Not a public endpoint: deployment requires RLS/migrations and rate limiting.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from database.models.document_issuance import DocumentIssuance
from database.models.file_management import ManagedFile
from services.document_issuance_integrity import (
    IssuanceFingerprint, verify_exact_document,
)
from services.file_service import read_file_bytes


def verify_stored_issuance(
    *, db: Session, authenticated_tenant_id: UUID,
    public_id: str, submitted_pdf: bytes | None = None,
) -> str:
    """Verify trusted record, private stored PDF, and optional submitted bytes.

    Never return 'verified' when the canonical private file is missing or
    modified; never claim exact-file verification from QR lookup alone.
    """
    if not isinstance(authenticated_tenant_id, UUID):
        raise ValueError("Authenticated tenant UUID required")
    if not isinstance(public_id, str) or not (12 <= len(public_id) <= 96):
        raise ValueError("Invalid public document identifier")
    record = (
        db.query(DocumentIssuance)
        .filter(
            DocumentIssuance.company_id == authenticated_tenant_id,
            DocumentIssuance.public_id == public_id,
        )
        .one_or_none()
    )
    if record is None:
        return "not_found"
    if record.status in {"revoked", "superseded"}:
        return record.status
    if record.status != "issued":
        return "unverified"
    try:
        file_id = UUID(record.artifact_key)
    except (TypeError, ValueError):
        return "unverified"
    file = (
        db.query(ManagedFile)
        .filter(
            ManagedFile.id == file_id,
            ManagedFile.company_id == authenticated_tenant_id,
            ManagedFile.is_deleted.is_(False),
            ManagedFile.visibility == "private",
            ManagedFile.is_confidential.is_(True),
        )
        .one_or_none()
    )
    if file is None:
        return "unavailable"
    canonical_pdf = read_file_bytes(file)
    expected = IssuanceFingerprint(
        tenant_id=authenticated_tenant_id,
        public_id=public_id,
        sha256_hex=record.final_pdf_sha256,
        status=record.status,
    )
    canonical_status = verify_exact_document(
        pdf=canonical_pdf, record=expected,
        expected_tenant_id=authenticated_tenant_id,
        requested_public_id=public_id,
    )
    if canonical_status != "verified":
        return "stored_document_integrity_failure"
    if submitted_pdf is None:
        return "issued_file_available_not_compared"
    return verify_exact_document(
        pdf=submitted_pdf, record=expected,
        expected_tenant_id=authenticated_tenant_id,
        requested_public_id=public_id,
    )
