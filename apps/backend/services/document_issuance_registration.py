"""Fail-closed registration of an already stored final PDF.

This is an internal service, not a public API. Caller must use an authorized
tenant-scoped DB transaction, and commit only after storing the immutable PDF
and issuing the event record. This service does not make mutable storage immutable.
Do not activate until migration/RLS and object-storage retention are certified.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, require_tenant_roles
from database.models.document_issuance import DocumentIssuance, DocumentIssuanceEvent
from database.models.file_management import ManagedFile
from services.document_issuance_integrity import new_public_document_id, pdf_fingerprint
from services.file_service import read_file_bytes


def register_stored_pdf_issuance(
    *, db: Session, context: TenantContext, managed_file_id: UUID,
    source_type: str, source_id: str, document_type: str,
    idempotency_key: str, version: int, stamp_configuration_version: int,
) -> DocumentIssuance:
    """Register exact bytes from the approved tenant's private ManagedFile.

    Never trust a PDF hash, issuer ID or tenant supplied by the browser.
    Returns an uncommitted ORM object; finalization must commit in caller's
    transaction. Unique constraint prevents racing idempotent inserts.
    """
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if context.is_platform_admin or context.staff is None or context.company_id is None:
        raise PermissionError("Tenant administrator required for issuance")
    for label, value, limit in (
        ("source_type", source_type, 80),
        ("source_id", source_id, 120),
        ("document_type", document_type, 80),
        ("idempotency_key", idempotency_key, 120),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"Invalid {label}")
    if (not isinstance(version, int) or isinstance(version, bool) or version < 1
            or not isinstance(stamp_configuration_version, int)
            or isinstance(stamp_configuration_version, bool)
            or stamp_configuration_version < 1):
        raise ValueError("Invalid version")
    existing = (
        db.query(DocumentIssuance)
        .filter(
            DocumentIssuance.company_id == context.company_id,
            DocumentIssuance.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if existing is not None:
        # Never approve a retry that refers to different data.
        if (existing.artifact_key != str(managed_file_id)
                or existing.source_type != source_type
                or existing.source_id != source_id
                or existing.document_type != document_type
                or existing.version != version
                or existing.stamp_configuration_version != stamp_configuration_version):
            raise ValueError("Idempotency key reused for a different document")
        return existing

    file = (
        db.query(ManagedFile)
        .filter(
            ManagedFile.id == managed_file_id,
            ManagedFile.company_id == context.company_id,
            ManagedFile.is_deleted.is_(False),
            ManagedFile.is_confidential.is_(True),
            ManagedFile.visibility == "private",
            ManagedFile.scan_status == "clean",
            ManagedFile.mime_type == "application/pdf",
        )
        .one_or_none()
    )
    if file is None or file.owner_user_id != context.user.id:
        raise PermissionError("Private, clean, tenant-owned final PDF required")
    content = read_file_bytes(file)
    digest = pdf_fingerprint(content)
    if digest != file.checksum_sha256:
        raise ValueError("Stored PDF fingerprint mismatch")

    entry = DocumentIssuance(
        company_id=context.company_id,
        public_id=new_public_document_id(),
        idempotency_key=idempotency_key,
        source_type=source_type,
        source_id=source_id,
        document_type=document_type,
        version=version,
        stamp_configuration_version=stamp_configuration_version,
        final_pdf_sha256=digest,
        artifact_key=str(managed_file_id),
        status="issued",
        issued_by_user_id=context.user.id,
    )
    db.add(entry)
    db.flush()
    db.add(DocumentIssuanceEvent(
        company_id=context.company_id,
        issuance_id=entry.id,
        event_type="issued",
        actor_user_id=context.user.id,
        detail="Exact-byte PDF hash registered against tenant private file",
    ))
    db.flush()
    return entry
