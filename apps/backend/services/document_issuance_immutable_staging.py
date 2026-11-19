"""Staging-only immutable write step for the LoanHub issuance pipeline.

Produces a quarantined *candidate*, never an issued document. The caller must
bind the exact S3 version and register the issuance/audit event in the same
authorized DB transaction. No API route invokes this step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, require_tenant_roles
from database.config.config import settings
from services.document_issuance_candidate import (
    PreparedDocumentCandidate, prepare_stamped_document_candidate,
)
from services.document_issuance_immutable_s3 import (
    LockedPdfObject, S3ObjectLockPdfStore,
)
from services.document_issuance_integrity import pdf_fingerprint
from services.document_issuance_stamp_snapshot import stamp_snapshot_sha256
from services.document_issuance_stamp_approval_repository import lookup_approved_stamp_from_database
from services.malware_scan_service import scan_upload
from services.object_storage_service import StorageUnavailableError


@dataclass(frozen=True)
class StagedLockedCandidate:
    candidate: PreparedDocumentCandidate
    locked: LockedPdfObject
    source_sha256_hex: str
    stamp_snapshot_sha256_hex: str


def stage_locked_document_candidate(
    *, context: TenantContext, source_pdf: bytes,
    trusted_verification_origin: str, store: S3ObjectLockPdfStore,
    db: Session, stamp_configuration_version: int,
) -> StagedLockedCandidate:
    """Write a locked exact PDF version after company and malware preflight.

    This function does NOT return a usable issued document. An object may
    remain orphaned if later SQL registration fails. Never delete that version
    on uncertain commit; reconcile by tenant, public ID, key and version.
    """
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if (
        context.is_platform_admin or not isinstance(context.company_id, UUID)
        or context.company is None or context.company.id != context.company_id
        or context.staff is None or context.user is None
    ):
        raise PermissionError("Authenticated tenant management context required")
    if not settings.MALWARE_SCAN_ENABLED or not settings.MALWARE_SCAN_FAIL_CLOSED:
        raise PermissionError("Official issuance requires enabled fail-closed malware scanning")
    if not isinstance(store, S3ObjectLockPdfStore):
        raise PermissionError("Official issuance staging requires the S3 Object Lock adapter")

    if type(stamp_configuration_version) is not int or stamp_configuration_version < 1:
        raise ValueError("Valid approved stamp configuration version required")
    # Use the same connected restricted PostgreSQL session as registration.
    # This forbids rendering and permanent retention of unapproved stamps.
    lookup_approved_stamp_from_database(
        db=db, company=context.company,
        authenticated_tenant_id=context.company_id,
        issuer_user_id=context.user.id,
        configuration_version=stamp_configuration_version,
    )
    # Resolve company fields BEFORE any non-reversible S3 Object Lock write.
    # Compare again after rendering to prevent a company-record mutation while
    # the certificate is assembled (a live approval check is still required).
    stamp_digest = stamp_snapshot_sha256(
        company=context.company, authenticated_tenant_id=context.company_id,
    )
    # Check the source itself, then the altered/stamped final PDF before
    # uploading; no 'validated' or scan-disabled result is acceptable.
    if scan_upload(source_pdf) != "clean":
        raise PermissionError("Source PDF malware scan did not complete as clean")
    candidate = prepare_stamped_document_candidate(
        source_pdf=source_pdf, company=context.company,
        authenticated_tenant_id=context.company_id,
        issued_at=datetime.now(timezone.utc),
        trusted_verification_origin=trusted_verification_origin,
    )
    if candidate.tenant_id != context.company_id:
        raise PermissionError("Rendered PDF company binding changed")
    if stamp_snapshot_sha256(
        company=context.company, authenticated_tenant_id=context.company_id,
    ) != stamp_digest:
        raise PermissionError("Company stamp changed while rendering the official PDF")
    if (not isinstance(candidate.public_id, str)
            or not (12 <= len(candidate.public_id) <= 96)
            or not all(c.isascii() and (c.isalnum() or c in "-_")
                       for c in candidate.public_id)):
        raise ValueError("Invalid official document public identity")
    # Never retain a document with a QR locator redirected to an attacker
    # or bound to a different public ID than the stored object key.
    origin = urlsplit(trusted_verification_origin) if isinstance(
        trusted_verification_origin, str
    ) else None
    if (origin is None or origin.scheme != "https" or not origin.hostname
            or origin.username or origin.password or origin.query or origin.fragment
            or origin.path not in ("", "/")):
        raise ValueError("Trusted HTTPS verification origin required")
    expected_url = (
        f"{trusted_verification_origin.rstrip('/')}/verify/{candidate.public_id}"
    )
    if candidate.verification_url != expected_url:
        raise ValueError("Rendered QR locator differs from approved verification identity")
    if not isinstance(candidate.pdf_bytes, bytes) or not candidate.pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("Rendered official document is not a PDF")
    if pdf_fingerprint(candidate.pdf_bytes) != candidate.sha256_hex:
        raise ValueError("Rendered official PDF fingerprint does not match candidate")
    if scan_upload(candidate.pdf_bytes) != "clean":
        raise PermissionError("Final PDF malware scan did not complete as clean")

    # Approval may be revoked while generating or scanning the PDF.
    # Recheck immediately before irreversible Object Lock retention; final
    # registration performs a further authoritative lookup before commit.
    lookup_approved_stamp_from_database(
        db=db, company=context.company,
        authenticated_tenant_id=context.company_id,
        issuer_user_id=context.user.id,
        configuration_version=stamp_configuration_version,
    )
    locked = store.put_locked_pdf(
        tenant_id=str(context.company_id), public_id=candidate.public_id,
        pdf=candidate.pdf_bytes,
    )
    # A COMPLIANCE upload ACK alone is not enough: compare exact read-by-version
    # to the candidate before it can even be presented to the DB binder.
    if store.read_exact_version(locked) != candidate.pdf_bytes:
        raise StorageUnavailableError("Exact locked PDF version differs from candidate")
    if locked.sha256_hex != candidate.sha256_hex:
        raise StorageUnavailableError("Locked PDF hash differs from candidate")
    return StagedLockedCandidate(
        candidate=candidate, locked=locked,
        source_sha256_hex=pdf_fingerprint(source_pdf),
        stamp_snapshot_sha256_hex=stamp_digest,
    )
