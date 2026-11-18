"""Staging-only immutable write step for the LoanHub issuance pipeline.

Produces a quarantined *candidate*, never an issued document. The caller must
bind the exact S3 version and register the issuance/audit event in the same
authorized DB transaction. No API route invokes this step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, require_tenant_roles
from database.config.config import settings
from services.document_issuance_candidate import (
    PreparedDocumentCandidate, prepare_stamped_document_candidate,
)
from services.document_issuance_immutable_s3 import (
    LockedPdfObject, S3ObjectLockPdfStore,
)
from services.document_issuance_integrity import pdf_fingerprint
from services.malware_scan_service import scan_upload
from services.object_storage_service import StorageUnavailableError


@dataclass(frozen=True)
class StagedLockedCandidate:
    candidate: PreparedDocumentCandidate
    locked: LockedPdfObject
    source_sha256_hex: str


def stage_locked_document_candidate(
    *, context: TenantContext, source_pdf: bytes,
    trusted_verification_origin: str, store: S3ObjectLockPdfStore,
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
    if scan_upload(candidate.pdf_bytes) != "clean":
        raise PermissionError("Final PDF malware scan did not complete as clean")

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
    )
