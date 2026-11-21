"""Non-routed source authorization for experimental immutable PDF issuance.

An untrusted PDF supplied by a caller is never evidence of ownership.
Resolve an existing private, scanned company-owned ManagedFile from the
authenticated tenant's database session, then verify the exact stored bytes.
Matching linked_entity_type/id is an integrity association, not proof that
the linkage was set by an authoritative generator. The
generator/source lifecycle and actual business-record authorization must be
reviewed before an issuance route exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, require_tenant_roles
from database.models.file_management import ManagedFile
from services.document_issuance_integrity import pdf_fingerprint
from services.file_service import read_file_bytes


@dataclass(frozen=True)
class AuthorizedManagedPdfSource:
    tenant_id: UUID
    source_file_id: UUID
    owner_user_id: UUID
    pdf_bytes: bytes
    sha256_hex: str
    source_type: str
    source_id: str


def load_authorized_managed_pdf_source(
    *, db: Session, context: TenantContext, source_file_id: UUID,
    source_type: str, source_id: str,
) -> AuthorizedManagedPdfSource:
    """Reject cross-tenant/unowned/unscanned source before reading its bytes."""
    for label, value, max_length in (
        ("source_type", source_type, 80),
        ("source_id", source_id, 120),
    ):
        if (not isinstance(value, str) or not value.strip()
                or value != value.strip() or len(value) > max_length):
            raise ValueError(f"Valid {label} required")
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if (context.is_platform_admin or not isinstance(context.company_id, UUID)
            or context.company is None or context.company.id != context.company_id
            or context.user is None or not isinstance(context.user.id, UUID)
            or context.staff is None or not isinstance(source_file_id, UUID)):
        raise PermissionError("Verified tenant-owned PDF source required")
    source = db.query(ManagedFile).filter(
        ManagedFile.id == source_file_id,
        ManagedFile.company_id == context.company_id,
        ManagedFile.owner_user_id == context.user.id,
        ManagedFile.is_deleted.is_(False),
        ManagedFile.is_confidential.is_(True),
        ManagedFile.visibility == "private",
        ManagedFile.scan_status == "clean",
        ManagedFile.mime_type == "application/pdf",
        ManagedFile.linked_entity_type == source_type,
        ManagedFile.linked_entity_id == source_id,
    ).one_or_none()
    if (source is None or source.id != source_file_id
            or source.company_id != context.company_id
            or source.owner_user_id != context.user.id
            or source.is_deleted is not False
            or source.is_confidential is not True
            or source.visibility != "private"
            or source.scan_status != "clean"
            or source.mime_type != "application/pdf"
            or source.linked_entity_type != source_type
            or source.linked_entity_id != source_id):
        raise PermissionError("Private, clean, tenant-owned source PDF required")
    contents = read_file_bytes(source)
    if not isinstance(contents, bytes) or not contents.startswith(b"%PDF-"):
        raise ValueError("Authorized source is not a PDF")
    digest = pdf_fingerprint(contents)
    if source.checksum_sha256 != digest:
        raise ValueError("Stored source PDF fingerprint mismatch")
    return AuthorizedManagedPdfSource(
        tenant_id=context.company_id, source_file_id=source_file_id,
        owner_user_id=context.user.id, pdf_bytes=contents, sha256_hex=digest,
        source_type=source_type, source_id=source_id,
    )


def stage_authorized_managed_pdf_source(
    *, db: Session, context: TenantContext, source_file_id: UUID,
    source_type: str, source_id: str,
    trusted_verification_origin: str, store,
    stamp_configuration_version: int,
):
    """Non-routed entry point; never accept arbitrary caller-supplied PDF bytes.

    The staging helper independently enforces company approval, malware scan,
    and exact S3 retention; this entry point provides its trusted source bytes.
    No official issuance/return of bytes occurs until later registration.
    """
    from services.document_issuance_immutable_staging import stage_locked_document_candidate

    source = load_authorized_managed_pdf_source(
        db=db, context=context, source_file_id=source_file_id,
        source_type=source_type, source_id=source_id,
    )
    return stage_locked_document_candidate(
        context=context, source_pdf=source.pdf_bytes,
        trusted_verification_origin=trusted_verification_origin,
        store=store, db=db,
        stamp_configuration_version=stamp_configuration_version,
    )
