"""Non-routed source lock for future official Document Studio letter issuance.

Caller must use an isolated issuer SQL transaction with narrow row-lock rights.
A locked source is not yet an issued PDF and MUST NOT be returned as approval
for an unrelated later transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from database.models.workspace_document import WorkspaceDocument, WorkspaceDocumentSignature


@dataclass(frozen=True)
class LockedLetterSource:
    tenant_id: UUID
    document_id: UUID
    version: int
    template_key: str
    content_sha256: str


def lock_current_letter_source(*, db, document, authenticated_tenant_id: UUID):
    """Lock and compare the *persisted* letter before official approval lookup."""
    document_id = getattr(document, "id", None)
    if not isinstance(document_id, UUID) or not isinstance(authenticated_tenant_id, UUID):
        raise PermissionError("Persisted letter identity required")
    row = (
        db.query(WorkspaceDocument)
        .filter(
            WorkspaceDocument.id == document_id,
            WorkspaceDocument.company_id == authenticated_tenant_id,
        )
        .populate_existing()
        .with_for_update(nowait=True)
        .one_or_none()
    )
    if row is None or row.company_id != authenticated_tenant_id:
        raise PermissionError("Authoritative tenant letter not found")
    if (row.is_deleted is not False or row.status != "draft"
            or row.finalized_at is not None
            or type(row.version) is not int or row.version < 1
            or not isinstance(row.content_html, str)):
        raise PermissionError("Current letter is deleted, finalized or invalid")
    for field in ("company_id", "template_key", "version", "content_html", "status", "finalized_at"):
        if getattr(document, field, None) != getattr(row, field):
            raise PermissionError("Letter content or version changed since preparation")
    # The document row is locked FOR UPDATE (stronger than FOR SHARE).
    # The FK from signatures.document_id requires parent KEY SHARE for new
    # inserts; this blocks competing signature INSERTs until COMMIT.
    signature = (
        db.query(WorkspaceDocumentSignature.id)
        .filter(WorkspaceDocumentSignature.document_id == document_id)
        .first()
    )
    if signature is not None:
        raise PermissionError("Stored letter signatures require separate issuance")
    return LockedLetterSource(
        tenant_id=authenticated_tenant_id,
        document_id=document_id,
        version=row.version,
        template_key=row.template_key,
        content_sha256=sha256(row.content_html.encode("utf-8")).hexdigest(),
    )
