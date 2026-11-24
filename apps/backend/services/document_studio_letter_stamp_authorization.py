"""Non-routed authorization preflight for future official client-letter issuance.

No public route calls this function. Returning a stamp does NOT constitute
issuance: a trusted issuer must still bind exact final PDF bytes, authorization
locks, immutable storage and audit registration in one controlled transaction.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.access_control import TenantContext
from uuid import UUID

from services.client_document_template_service import CLIENT_LETTER_TEMPLATE_KEYS
from services.company_stamp_configuration import stamp_from_company
from services.document_issuance_stamp_approval_repository import (
    lookup_approved_stamp_from_database,
)
from services.document_issuance_stamp_snapshot import stamp_snapshot_sha256
from services.document_issuance_trusted_login import require_trusted_issuer_database_login
from services.document_issuance_role_tenant_binding import require_issuer_role_tenant_binding
from services.document_studio_letter_source_lock import lock_current_letter_source, LockedLetterSource
from services.document_issuance_issuer_authorization import require_current_document_issuer
from services.document_issuance_transaction_guard import (
    read_issuer_transaction_identity, require_same_issuer_transaction,
)


LETTER_TEMPLATES = frozenset(CLIENT_LETTER_TEMPLATE_KEYS | {
    "formal_letter", "business_letter",
})


@dataclass(frozen=True)
class AuthorizedLetterStamp:
    """Immutable approval evidence for a later, separately secured issuer."""

    tenant_id: UUID
    configuration_version: int
    stamp_snapshot_sha256: str
    legal_name: str
    approved_by_user_id: UUID
    source: LockedLetterSource


def preflight_approved_letter_stamp(
    *, db, context: TenantContext, document, company,
    authenticated_tenant_id: UUID, issuer_user_id: UUID,
    configuration_version: int,
) -> AuthorizedLetterStamp:
    """Validate tenant-scoped approval. Never stamp or persist a PDF here."""
    if not isinstance(authenticated_tenant_id, UUID) or not isinstance(issuer_user_id, UUID):
        raise PermissionError("Verified tenant and issuer required")
    if (not isinstance(context, TenantContext)
            or context.is_platform_admin
            or context.company_id != authenticated_tenant_id
            or context.user is None or context.user.id != issuer_user_id
            or context.company is None or context.company.id != authenticated_tenant_id):
        raise PermissionError("Authenticated company staff context required")
    if (getattr(document, "company_id", None) != authenticated_tenant_id
            or company is None or getattr(company, "id", None) != authenticated_tenant_id):
        raise PermissionError("Letter and company must belong to authenticated tenant")
    if getattr(document, "template_key", None) not in LETTER_TEMPLATES:
        raise PermissionError("Only supported company letters may use this stamp gate")
    if (getattr(document, "finalized_at", None) is not None
            or getattr(document, "status", None) != "draft"):
        raise PermissionError("Official letter issuance requires a draft source")
    # A caller must provide an authoritative signature-state check before
    # issuing; this preflight refuses documents exposing any signature rows.
    # A separately trusted issuer must still lock/recheck persisted signatures.
    if getattr(document, "signatures", None):
        raise PermissionError("Signed letters require separate issuance verification")
    if type(configuration_version) is not int or configuration_version < 1:
        raise PermissionError("Approved stamp configuration version required")

    # Tenant GUCs alone are spoofable by the shared application DB login.
    # This must run on a separately provisioned, narrowly authorized issuer
    # connection, never the ordinary LoanHub runtime pool.
    require_trusted_issuer_database_login(db=db)
    # A protected, administrator-owned SQL-login mapping binds this DB role
    # to exactly one company. A caller-controlled tenant GUC cannot replace it.
    require_issuer_role_tenant_binding(db=db, authenticated_tenant_id=authenticated_tenant_id)
    # Re-read active user, approved company and management membership under
    # SHARE NOWAIT locks on the SAME isolated issuer transaction.
    authorized = require_current_document_issuer(db=db, context=context)
    if authorized.user_id != issuer_user_id or authorized.company_id != authenticated_tenant_id:
        raise PermissionError("Current issuer does not match authenticated company")
    root_transaction = db.get_transaction()
    if root_transaction is None:
        raise PermissionError("Issuer row locks require an active SQL transaction")
    transaction_identity = read_issuer_transaction_identity(db=db)
    # Acquire the protected, tenant-bound SQL source lock before reading the
    # persisted version. It holds FOR UPDATE within the SECURITY DEFINER
    # function, without granting the issuer direct source-table UPDATE.
    # The subsequent ORM source read also requires verified tenant RLS.
    locked_source = lock_current_letter_source(
        db=db, document=document, authenticated_tenant_id=authenticated_tenant_id,
    )
    if locked_source.template_key not in LETTER_TEMPLATES:
        raise PermissionError("Unsupported persisted letter template")

    # The existing repository checks connected SQL identity, tenant RLS,
    # restricted SELECT-only privileges, approval version, snapshot digest,
    # independent approver, expiry and revocation.
    approval = lookup_approved_stamp_from_database(
        db=db, company=company, authenticated_tenant_id=authenticated_tenant_id,
        issuer_user_id=issuer_user_id, configuration_version=configuration_version,
    )
    # Resolve the same company snapshot after the approval check. The future
    # issuer MUST recheck within its own guarded transaction before commit.
    stamp = stamp_from_company(company, authenticated_tenant_id=authenticated_tenant_id)
    digest = stamp_snapshot_sha256(
        company=company, authenticated_tenant_id=authenticated_tenant_id,
    )
    if digest != approval.snapshot_sha256_hex:
        raise PermissionError("Company stamp changed during authorization")
    if db.get_transaction() is not root_transaction:
        raise PermissionError("Issuer authorization transaction was replaced")
    require_same_issuer_transaction(db=db, expected=transaction_identity)
    return AuthorizedLetterStamp(
        tenant_id=authenticated_tenant_id,
        configuration_version=configuration_version,
        stamp_snapshot_sha256=digest,
        legal_name=stamp.legal_name,
        approved_by_user_id=approval.approved_by_user_id,
        source=locked_source,
    )
