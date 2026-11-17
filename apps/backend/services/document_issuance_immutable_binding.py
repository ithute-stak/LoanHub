"""Validated binding between an issuance row and an S3 Object Lock version.

Staging-only bridge; no public route and no activation of the ordinary
ManagedFile finalizer. The immutable object reference and final SHA-256 must
match the already-approved candidate before registration can commit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from database.models.document_issuance import DocumentIssuance
from services.document_issuance_immutable_s3 import LockedPdfObject, S3ObjectLockPdfStore
from services.document_issuance_integrity import pdf_fingerprint
from services.object_storage_service import StorageUnavailableError


def bind_locked_pdf_to_issuance(
    *, issuance: DocumentIssuance, tenant_id: UUID, candidate_pdf: bytes,
    locked: LockedPdfObject, store: S3ObjectLockPdfStore,
) -> None:
    """Bind only after reading the actual locked version and validating bytes.

    The caller must own the tenant-authorized SQL transaction and commit the
    issuance together with its audit event. No storage-delete compensation on
    uncertain DB commits: reconcile by immutable key and version instead.
    """
    if not isinstance(tenant_id, UUID) or issuance.company_id != tenant_id:
        raise PermissionError("Issuance does not belong to authenticated tenant")
    if issuance.status != "issued":
        raise ValueError("Only a newly issued document can bind immutable storage")
    if not isinstance(candidate_pdf, bytes):
        raise ValueError("Official PDF bytes required")
    if locked.bucket != store.bucket:
        raise PermissionError("Immutable artifact bucket is not approved")
    if locked.key != store._key(str(tenant_id), issuance.public_id):
        raise PermissionError("Immutable artifact identity does not match issuance")
    if (not locked.version_id or locked.version_id == "null"
            or not isinstance(locked.retain_until, datetime)
            or locked.retain_until.tzinfo is None
            or locked.retain_until.astimezone(timezone.utc) <= datetime.now(timezone.utc)):
        raise ValueError("Unusable immutable object version or retention")
    digest = pdf_fingerprint(candidate_pdf)
    if issuance.final_pdf_sha256 != digest or locked.sha256_hex != digest:
        raise ValueError("Candidate and issuance SHA-256 differ from immutable artifact")
    if any((
        issuance.immutable_bucket, issuance.immutable_object_key,
        issuance.immutable_version_id, issuance.immutable_retain_until,
    )):
        raise ValueError("Issuance immutable reference is already bound")

    exact = store.read_exact_version(locked)
    if exact != candidate_pdf:
        raise StorageUnavailableError("Locked object version differs from issued PDF")

    issuance.immutable_bucket = locked.bucket
    issuance.immutable_object_key = locked.key
    issuance.immutable_version_id = locked.version_id
    issuance.immutable_retain_until = locked.retain_until


def verify_locked_pdf_for_issuance(
    *, issuance: DocumentIssuance, tenant_id: UUID,
    store: S3ObjectLockPdfStore,
) -> bytes:
    """Fetch exact provider version. Never fall back to mutable latest-key read."""
    if not isinstance(tenant_id, UUID) or issuance.company_id != tenant_id:
        raise PermissionError("Cross-company document verification denied")
    if issuance.status != "issued":
        raise ValueError("Inactive issuance is not verifiable as currently issued")
    if (not issuance.immutable_bucket or not issuance.immutable_object_key
            or not issuance.immutable_version_id or not issuance.immutable_retain_until):
        raise StorageUnavailableError("Issuance immutable artifact reference is incomplete")
    if issuance.immutable_bucket != store.bucket:
        raise PermissionError("Stored artifact belongs to another storage bucket")
    if issuance.immutable_object_key != store._key(str(tenant_id), issuance.public_id):
        raise PermissionError("Stored artifact identity does not match issuance")
    locked = LockedPdfObject(
        bucket=issuance.immutable_bucket,
        key=issuance.immutable_object_key,
        version_id=issuance.immutable_version_id,
        sha256_hex=issuance.final_pdf_sha256,
        retain_until=issuance.immutable_retain_until,
    )
    pdf = store.read_exact_version(locked)
    if pdf_fingerprint(pdf) != issuance.final_pdf_sha256:
        raise StorageUnavailableError("Official PDF immutable version is altered")
    return pdf
