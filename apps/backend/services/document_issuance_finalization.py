"""Experimental backend-only finalization transaction for LoanHub PDFs.

Not routed or enabled until the reviewed schema migration, RLS, company
approval, object immutability, and end-to-end checks have shipped.

Database and object storage are distinct transactional systems. A successful DB
commit is the issuance linearization point; uncertain commit outcomes must be
reconciled by the immutable ID and idempotency key. Do not destroy any stored
object after an uncertain commit outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, require_tenant_roles
from services.document_issuance_candidate import prepare_stamped_document_candidate
from services.document_issuance_integrity import pdf_fingerprint
from services.document_issuance_registration import register_stored_pdf_issuance
from services.file_service import read_file_bytes, store_bytes


@dataclass(frozen=True)
class CommittedDocument:
    public_id: str
    issuance_id: UUID
    managed_file_id: UUID
    sha256_hex: str
    document_bytes: bytes


def finalize_and_register_document(
    *, db: Session, context: TenantContext, source_pdf: bytes,
    trusted_verification_origin: str, source_type: str, source_id: str,
    document_type: str, idempotency_key: str, version: int,
    stamp_configuration_version: int,
) -> CommittedDocument:
    """Return official bytes only once all issuance writes have committed.

    Restricted to company management until delegated staff issuance approvals
    have been implemented and security tested. Never pass a client supplied
    company or issuing user. Storage retention policy must be configured
    externally. A failure after object upload may leave an orphan to reconcile.
    """
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if (context.is_platform_admin or context.company_id is None
            or context.company is None or context.staff is None
            or context.company.id != context.company_id):
        raise PermissionError("A verified active company context is required")
    if not isinstance(source_pdf, bytes):
        raise ValueError("PDF bytes are required")
    # Registration also validates these fields, but do so *before* writing an
    # object so malformed request inputs cannot create orphan storage.
    for label, value, limit in (
        ("source_type", source_type, 80),
        ("source_id", source_id, 120),
        ("document_type", document_type, 80),
        ("idempotency_key", idempotency_key, 120),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"Invalid {label}")
    if (type(version) is not int or version < 1
            or type(stamp_configuration_version) is not int
            or stamp_configuration_version < 1):
        raise ValueError("Invalid document version")

    # No preliminary response, URL, or "verified" flag escapes this service.
    # The rendered QR and persisted issuance share the same freshly allocated ID.
    candidate = prepare_stamped_document_candidate(
        source_pdf=source_pdf, company=context.company,
        authenticated_tenant_id=context.company_id,
        issued_at=datetime.now(timezone.utc),
        trusted_verification_origin=trusted_verification_origin,
    )
    # ManagedFile may be stored encrypted. The digest is of its plaintext PDF.
    # The existing store_bytes service performs MIME and malware checks.
    try:
        managed_file = store_bytes(
            db, content=candidate.pdf_bytes,
            original_name=f"loanhub-issued-{candidate.public_id}.pdf",
            mime_type="application/pdf",
            owner_user_id=context.user.id,
            company_id=context.company_id,
            branch_id=context.branch_id,
            category="official_document_issuance",
            visibility="private",
            description="Official LoanHub tenant PDF issuance",
            linked_entity_type=source_type,
            linked_entity_id=source_id,
            is_confidential=True,
        )
        if managed_file.scan_status != "clean":
            raise ValueError("Official document requires a clean malware scan")
        # Verify a second read from canonical object storage before committing
        # and before returning any bytes to the caller.
        stored = read_file_bytes(managed_file)
        if pdf_fingerprint(stored) != candidate.sha256_hex:
            raise ValueError("Canonical PDF bytes changed before issuance")
        issuance = register_stored_pdf_issuance(
            db=db, context=context,
            managed_file_id=managed_file.id,
            source_type=source_type, source_id=source_id,
            document_type=document_type,
            idempotency_key=idempotency_key, version=version,
            stamp_configuration_version=stamp_configuration_version,
            public_id=candidate.public_id,
        )
        if (issuance.final_pdf_sha256 != candidate.sha256_hex
                or issuance.public_id != candidate.public_id
                or issuance.artifact_key != str(managed_file.id)):
            raise ValueError("Issuance record and PDF candidate disagree")
        db.commit()
    except Exception:
        db.rollback()
        # Do not delete stored objects here: failure may have occurred during
        # an uncertain COMMIT and the record may already be durable.
        raise

    return CommittedDocument(
        public_id=issuance.public_id,
        issuance_id=issuance.id,
        managed_file_id=managed_file.id,
        sha256_hex=issuance.final_pdf_sha256,
        document_bytes=stored,
    )
