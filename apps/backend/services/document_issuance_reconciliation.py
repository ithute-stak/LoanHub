"""Read-only recovery assessment for a staged Object Lock PDF.

Use after SQL commit uncertainty or when an immutable upload has no known
issuance row. This does not retry issuance, delete retained objects, expose
PDF bytes, or decide that an object is safe to discard. A missing record can
also mean replica lag, transaction uncertainty, or an inaccessible tenant
scope: it is NEVER evidence that deleting the locked version is safe.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.document_issuance import DocumentIssuance
from services.document_issuance_database_readiness import require_document_issuance_database_ready
from services.document_issuance_immutable_s3 import LockedPdfObject, S3ObjectLockPdfStore
from services.document_issuance_integrity import pdf_fingerprint
from services.object_storage_service import StorageUnavailableError


@dataclass(frozen=True)
class LockedIssuanceRecoveryAssessment:
    public_id: str
    status: str
    # An assessment does not authorize automatic deletion/retry/reissue.
    manual_review_required: bool = True


def assess_locked_issuance_recovery(
    *, db: Session, authenticated_tenant_id: UUID,
    public_id: str, locked: LockedPdfObject,
    store: S3ObjectLockPdfStore,
) -> LockedIssuanceRecoveryAssessment:
    """Check authoritative tenant-scoped SQL and exact S3 object version.

    The caller MUST bind verified PostgreSQL tenant context to the session;
    this module never takes a tenant ID from request headers. No mutations.
    """
    if not isinstance(authenticated_tenant_id, UUID):
        raise PermissionError("Authenticated tenant required")
    if not isinstance(store, S3ObjectLockPdfStore):
        raise PermissionError("Certified Object Lock adapter required")
    if not isinstance(public_id, str) or not (12 <= len(public_id) <= 96):
        raise ValueError("Valid public document ID required")
    if (locked.bucket != store.bucket
            or locked.key != store._key(str(authenticated_tenant_id), public_id)
            or not locked.version_id or locked.version_id == "null"):
        raise PermissionError("Immutable artifact identity mismatch")

    require_document_issuance_database_ready(db)
    record = db.query(DocumentIssuance).filter(
        DocumentIssuance.company_id == authenticated_tenant_id,
        DocumentIssuance.public_id == public_id,
    ).one_or_none()

    if record is None:
        return LockedIssuanceRecoveryAssessment(
            public_id=public_id, status="unregistered_locked_object_review",
        )
    if record.company_id != authenticated_tenant_id:
        raise PermissionError("Record belongs to a different tenant")
    if (record.immutable_bucket != locked.bucket
            or record.immutable_object_key != locked.key
            or record.immutable_version_id != locked.version_id
            or record.final_pdf_sha256 != locked.sha256_hex):
        return LockedIssuanceRecoveryAssessment(
            public_id=public_id, status="registered_reference_mismatch",
        )
    if record.status != "issued":
        return LockedIssuanceRecoveryAssessment(
            public_id=public_id, status="registered_inactive",
        )
    try:
        exact_pdf = store.read_exact_version(locked)
        if pdf_fingerprint(exact_pdf) != record.final_pdf_sha256:
            return LockedIssuanceRecoveryAssessment(
                public_id=public_id, status="registered_digest_mismatch",
            )
    except (StorageUnavailableError, ValueError, OSError):
        return LockedIssuanceRecoveryAssessment(
            public_id=public_id, status="locked_version_unavailable",
        )
    return LockedIssuanceRecoveryAssessment(
        public_id=public_id, status="registered_version_verified",
        manual_review_required=False,
    )
