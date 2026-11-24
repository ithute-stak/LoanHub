"""Non-routed, transaction-guarded evidence for a rendered company letter.

Not an issuance endpoint and does not grant stamp approval. The separately
trusted issuer must hold DB locks through final immutable registration COMMIT.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from uuid import UUID

from services.document_issuance_integrity import pdf_fingerprint
from services.document_issuance_transaction_guard import (
    read_issuer_transaction_identity, require_same_issuer_transaction,
)
from services.document_studio_letter_render_snapshot import letter_render_snapshot_sha256
from services.document_studio_letter_stamp_authorization import AuthorizedLetterStamp
from services.document_studio_letter_render_evidence import (
    RenderedLetterCandidate, render_letter_pdf_with_header_evidence,
)


@dataclass(frozen=True)
class TransactionBoundLetterRender:
    tenant_id: UUID
    document_id: UUID
    version: int
    source_html_sha256: str
    render_snapshot_sha256: str
    header_branding_sha256: str
    rendered_pdf_sha256: str
    approved_stamp_snapshot_sha256: str
    pdf_bytes: bytes


def render_authorized_letter_evidence(
    *, db, authorized_stamp: AuthorizedLetterStamp,
    document, company, authenticated_tenant_id: UUID,
) -> TransactionBoundLetterRender:
    """Render inside one already-authorized isolated SQL transaction.

    Requires an actual locked *persisted* document, not an untrusted payload.
    The caller must retain the issuer/source locks and repeat approval and
    transaction checks before an eventual separately implemented COMMIT.
    """
    if not isinstance(authorized_stamp, AuthorizedLetterStamp):
        raise PermissionError("Authoritative letter preflight required")
    locked = authorized_stamp.source
    if (not isinstance(authenticated_tenant_id, UUID)
            or authorized_stamp.tenant_id != authenticated_tenant_id
            or locked.tenant_id != authenticated_tenant_id
            or not isinstance(locked.document_id, UUID)
            or getattr(document, "id", None) != locked.document_id
            or getattr(document, "company_id", None) != authenticated_tenant_id
            or getattr(company, "id", None) != authenticated_tenant_id
            or getattr(document, "version", None) != locked.version
            or getattr(document, "template_key", None) != locked.template_key):
        raise PermissionError("Authorized letter source or company mismatch")
    if not isinstance(getattr(document, "content_html", None), str):
        raise PermissionError("Authoritative letter HTML required")
    current_html_digest = sha256(document.content_html.encode("utf-8")).hexdigest()
    if not compare_digest(locked.content_sha256, current_html_digest):
        raise PermissionError("Authorized letter HTML changed after locking")
    current_snapshot_digest = letter_render_snapshot_sha256(document)
    if not compare_digest(locked.render_snapshot_sha256, current_snapshot_digest):
        raise PermissionError("Authorized letter rendering settings changed after locking")
    root_transaction = db.get_transaction()
    if root_transaction is None:
        raise PermissionError("Active isolated issuer transaction required")
    sql_transaction = read_issuer_transaction_identity(db=db)

    rendered: RenderedLetterCandidate = render_letter_pdf_with_header_evidence(
        db=db, document=document, company=company,
        authenticated_tenant_id=authenticated_tenant_id,
    )

    if (not isinstance(rendered, RenderedLetterCandidate)
            or rendered.tenant_id != authenticated_tenant_id
            or rendered.header_branding.tenant_id != authenticated_tenant_id
            or not compare_digest(pdf_fingerprint(rendered.pdf_bytes), rendered.pdf_sha256)):
        raise PermissionError("Renderer output or PDF evidence invalid")
    # Rendering could indirectly alter or expire our transaction. Never return
    # a usable candidate if the row locks may have been lost.
    if db.get_transaction() is not root_transaction:
        raise PermissionError("Issuer SQLAlchemy transaction replaced during rendering")
    require_same_issuer_transaction(db=db, expected=sql_transaction)
    if (not compare_digest(
            current_html_digest,
            sha256(document.content_html.encode("utf-8")).hexdigest(),
        ) or not compare_digest(
            current_snapshot_digest, letter_render_snapshot_sha256(document),
        )):
        raise PermissionError("Letter changed during PDF rendering")
    return TransactionBoundLetterRender(
        tenant_id=authenticated_tenant_id,
        document_id=locked.document_id,
        version=locked.version,
        source_html_sha256=current_html_digest,
        render_snapshot_sha256=current_snapshot_digest,
        header_branding_sha256=rendered.header_branding.combined_sha256,
        rendered_pdf_sha256=rendered.pdf_sha256,
        approved_stamp_snapshot_sha256=authorized_stamp.stamp_snapshot_sha256,
        pdf_bytes=rendered.pdf_bytes,
    )
