"""Non-routed authorization preflight for future official client-letter issuance.

No public route calls this function. Returning a stamp does NOT constitute
issuance: a trusted issuer must still bind exact final PDF bytes, authorization
locks, immutable storage and audit registration in one controlled transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from services.client_document_template_service import CLIENT_LETTER_TEMPLATE_KEYS
from services.company_stamp_configuration import stamp_from_company
from services.document_issuance_stamp_approval_repository import (
    lookup_approved_stamp_from_database,
)
from services.document_issuance_stamp_snapshot import stamp_snapshot_sha256


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


def preflight_approved_letter_stamp(
    *, db, document, company, authenticated_tenant_id: UUID,
    issuer_user_id: UUID, configuration_version: int,
) -> AuthorizedLetterStamp:
    """Validate tenant-scoped approval. Never stamp or persist a PDF here."""
    if not isinstance(authenticated_tenant_id, UUID) or not isinstance(issuer_user_id, UUID):
        raise PermissionError("Verified tenant and issuer required")
    if (getattr(document, "company_id", None) != authenticated_tenant_id
            or company is None or getattr(company, "id", None) != authenticated_tenant_id):
        raise PermissionError("Letter and company must belong to authenticated tenant")
    if getattr(document, "template_key", None) not in LETTER_TEMPLATES:
        raise PermissionError("Only supported company letters may use this stamp gate")
    if (getattr(document, "finalized_at", None) is not None
            or getattr(document, "status", None) != "draft"):
        raise PermissionError("Official letter issuance requires a draft source")
    if type(configuration_version) is not int or configuration_version < 1:
        raise PermissionError("Approved stamp configuration version required")

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
    return AuthorizedLetterStamp(
        tenant_id=authenticated_tenant_id,
        configuration_version=configuration_version,
        stamp_snapshot_sha256=digest,
        legal_name=stamp.legal_name,
        approved_by_user_id=approval.approved_by_user_id,
    )
