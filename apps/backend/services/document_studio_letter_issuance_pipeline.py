"""Non-routed company-letter issuance orchestration.

This function is deliberately NOT exposed through a route. It requires a
separately provisioned trusted issuer SQL login, approved stamp tables,
mandatory fail-closed malware scanning, versioned S3 Object Lock and
authoritative tenant staffing. None of those may be bypassed for production.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from uuid import UUID

from core.access_control import TenantContext
from services.document_issuance_integrity import pdf_fingerprint
from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore
from services.document_issuance_immutable_staging import stage_locked_document_candidate
from services.document_issuance_locked_registration import (
    CommittedLockedIssuance, register_locked_staged_document,
)
from services.document_issuance_transaction_guard import (
    read_issuer_transaction_identity, require_same_issuer_transaction,
)
from services.document_studio_letter_render_snapshot import letter_render_snapshot_sha256
from services.document_studio_letter_stamp_authorization import (
    preflight_approved_letter_stamp,
)
from services.document_studio_letter_transaction_render import (
    render_authorized_letter_evidence,
)


def issue_approved_company_letter_locked(
    *, db, context: TenantContext, document, company,
    authenticated_tenant_id: UUID, issuer_user_id: UUID,
    configuration_version: int, store: S3ObjectLockPdfStore,
    verification_origin: str, idempotency_key: str,
) -> CommittedLockedIssuance:
    """Guard one letter from persisted source lock to immutable SQL COMMIT.

    This boundary is not safe to route until deployed role grants, full
    renderer/cover-asset provenance, source revocation and verification
    endpoint have passed production-like end-to-end acceptance.
    """
    if (not isinstance(context, TenantContext)
            or context.is_platform_admin
            or context.company_id != authenticated_tenant_id
            or context.user is None or context.user.id != issuer_user_id
            or context.company is None or context.company.id != authenticated_tenant_id
            or company is not context.company):
        raise PermissionError("Authenticated issuer and company context required")
    if not isinstance(store, S3ObjectLockPdfStore):
        raise PermissionError("Immutable Object Lock store required")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise PermissionError("Idempotent issuance request required")

    # Trust gate, current issuer locks, persisted source version lock,
    # independent stamp approval and PostgreSQL XID are checked here.
    authorized = preflight_approved_letter_stamp(
        db=db, context=context, document=document, company=company,
        authenticated_tenant_id=authenticated_tenant_id,
        issuer_user_id=issuer_user_id,
        configuration_version=configuration_version,
    )
    transaction = db.get_transaction()
    if transaction is None:
        raise PermissionError("Locked issuer SQL transaction required")
    identity = read_issuer_transaction_identity(db=db)
    rendered = render_authorized_letter_evidence(
        db=db, authorized_stamp=authorized, document=document,
        company=company, authenticated_tenant_id=authenticated_tenant_id,
    )
    if (rendered.tenant_id != authenticated_tenant_id
            or rendered.document_id != authorized.source.document_id
            or rendered.version != authorized.source.version
            or not compare_digest(rendered.source_html_sha256, authorized.source.content_sha256)
            or not compare_digest(rendered.render_snapshot_sha256, authorized.source.render_snapshot_sha256)
            or not compare_digest(rendered.approved_stamp_snapshot_sha256, authorized.stamp_snapshot_sha256)
            or not compare_digest(rendered.rendered_pdf_sha256, pdf_fingerprint(rendered.pdf_bytes))):
        raise PermissionError("Letter render differs from approved persisted source")

    # The staging helper scans source and stamped bytes, verifies approval
    # again and binds read-back of the exact locked S3 object version.
    staged = stage_locked_document_candidate(
        context=context, source_pdf=rendered.pdf_bytes,
        trusted_verification_origin=verification_origin,
        store=store, db=db, stamp_configuration_version=configuration_version,
    )
    if (staged.candidate.tenant_id != authenticated_tenant_id
            or not compare_digest(staged.source_sha256_hex, rendered.rendered_pdf_sha256)
            or not compare_digest(staged.stamp_snapshot_sha256_hex, authorized.stamp_snapshot_sha256)):
        raise PermissionError("Staged official letter differs from approved source")
    # Staging could be slow: ensure no rollback/COMMIT switched us to a
    # different transaction while holding the persisted letter row lock.
    if db.get_transaction() is not transaction:
        raise PermissionError("Letter issuer transaction changed during staging")
    require_same_issuer_transaction(db=db, expected=identity)
    if (sha256(document.content_html.encode("utf-8")).hexdigest()
            != authorized.source.content_sha256
            or letter_render_snapshot_sha256(document)
            != authorized.source.render_snapshot_sha256):
        raise PermissionError("Persisted letter changed during immutable staging")

    # The generic non-routed registrar rechecks SQL authority/approval and
    # exact S3 version again before its own SQL COMMIT and audit registration.
    return register_locked_staged_document(
        db=db, context=context, staged=staged, store=store,
        source_pdf=rendered.pdf_bytes, source_type="workspace_document",
        source_id=str(authorized.source.document_id),
        document_type=authorized.source.template_key,
        idempotency_key=idempotency_key,
        version=authorized.source.version,
        stamp_configuration_version=configuration_version,
    )
