"""Experimental, NON-ROUTED registration of a locked official PDF candidate.

This helper intentionally does NOT enable public issuance or replace existing
LoanHub document flows. Its caller must validate source provenance, company
authorized source provenance and production Object Lock retention independently. A failed or
uncertain commit may leave a retained S3 object, to reconcile by public ID and
object VersionId; NEVER delete or return it as an issued PDF.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, require_tenant_roles
from database.models.document_issuance import DocumentIssuance, DocumentIssuanceEvent
from services.document_issuance_database_readiness import require_document_issuance_database_ready
from services.document_issuance_immutable_binding import bind_locked_pdf_to_issuance
from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore
from services.document_issuance_immutable_staging import StagedLockedCandidate
from services.document_issuance_integrity import pdf_fingerprint
from services.document_issuance_stamp_snapshot import stamp_snapshot_sha256
from services.document_issuance_stamp_approval_repository import lookup_approved_stamp_from_database


@dataclass(frozen=True)
class CommittedLockedIssuance:
    issuance_id: UUID
    public_id: str
    sha256_hex: str
    immutable_version_id: str
    document_bytes: bytes


def register_locked_staged_document(
    *, db: Session, context: TenantContext,
    staged: StagedLockedCandidate, store: S3ObjectLockPdfStore,
    source_pdf: bytes, source_type: str, source_id: str,
    document_type: str, idempotency_key: str, version: int,
    stamp_configuration_version: int,
) -> CommittedLockedIssuance:
    """Commit a tenant's immutable version and audit event atomically in SQL.

    Does not alter or remove the retained object on failed/uncertain commit.
    SQL uniqueness constraints remain the concurrency/idempotency authority.
    """
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if (context.is_platform_admin or not isinstance(context.company_id, UUID)
            or context.company is None or context.company.id != context.company_id
            or context.user is None or context.staff is None):
        raise PermissionError("Verified tenant company management required")
    if not isinstance(store, S3ObjectLockPdfStore):
        raise PermissionError("A dedicated immutable Object Lock adapter is required")
    if staged.candidate.tenant_id != context.company_id:
        raise PermissionError("Candidate belongs to another tenant")
    if not isinstance(staged.candidate.public_id, str) or not (
        12 <= len(staged.candidate.public_id) <= 96
    ):
        raise ValueError("Invalid issued document identity")
    if not isinstance(source_pdf, bytes):
        raise ValueError("Original source PDF bytes are required")
    source_digest = pdf_fingerprint(source_pdf)
    if staged.source_sha256_hex != source_digest:
        raise ValueError("Source PDF differs from the originally scanned staged source")
    if staged.stamp_snapshot_sha256_hex != stamp_snapshot_sha256(
        company=context.company, authenticated_tenant_id=context.company_id,
    ):
        raise ValueError("Company stamp fields changed after locked PDF staging")
    final_bytes = staged.candidate.pdf_bytes
    final_digest = pdf_fingerprint(final_bytes)
    if final_digest != staged.candidate.sha256_hex:
        raise ValueError("Untrusted candidate fingerprint")
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
        raise ValueError("Invalid issuance version")

    # The connected session must have real tenant RLS, non-owner privileges,
    # and no unrestricted update/delete access.
    require_document_issuance_database_ready(db)
    # Never accept approval data from callers: look up the exact approved
    # version and any revocation with the connected restricted SQL session.
    # This fails closed until the approval tables and runtime grants exist.
    lookup_approved_stamp_from_database(
        db=db, company=context.company,
        authenticated_tenant_id=context.company_id,
        issuer_user_id=context.user.id,
        configuration_version=stamp_configuration_version,
    )
    previous = db.query(DocumentIssuance).filter(
        DocumentIssuance.company_id == context.company_id,
        DocumentIssuance.idempotency_key == idempotency_key,
    ).one_or_none()
    if previous is not None:
        raise ValueError("Document request already registered; never silently reissue")

    # No bytes or official confirmation are returned before the SQL commit.
    try:
        issuance = DocumentIssuance(
            company_id=context.company_id,
            public_id=staged.candidate.public_id,
            idempotency_key=idempotency_key,
            source_type=source_type, source_id=source_id,
            document_type=document_type, version=version,
            stamp_configuration_version=stamp_configuration_version,
            source_pdf_sha256=source_digest, final_pdf_sha256=final_digest,
            artifact_key=str(staged.locked.version_id),
            status="issued", issued_by_user_id=context.user.id,
        )
        # Before writing anything to the database, bind only a version whose
        # exact bytes match the supplied candidate.
        bind_locked_pdf_to_issuance(
            issuance=issuance, tenant_id=context.company_id,
            candidate_pdf=final_bytes, locked=staged.locked, store=store,
        )
        db.add(issuance)
        db.flush()
        db.add(DocumentIssuanceEvent(
            company_id=context.company_id, issuance_id=issuance.id,
            event_type="issued", actor_user_id=context.user.id,
            detail="Immutable S3 Object Lock version bound and exact bytes checked",
        ))
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        # No S3 delete: the transaction outcome may be uncertain.
        raise

    return CommittedLockedIssuance(
        issuance_id=issuance.id, public_id=issuance.public_id,
        sha256_hex=final_digest,
        immutable_version_id=staged.locked.version_id,
        document_bytes=final_bytes,
    )
