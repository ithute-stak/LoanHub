"""Non-routed, pure exact-byte evidence for a locked letter's PDF candidate.

This is NOT official issuance or a signature. The future trusted issuer must
verify source locks, approval and storage transaction through final COMMIT.
"""
from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
from uuid import UUID

from services.document_issuance_integrity import pdf_fingerprint
from services.document_studio_letter_source_lock import LockedLetterSource


@dataclass(frozen=True)
class LockedLetterPdfEvidence:
    tenant_id: UUID
    document_id: UUID
    document_version: int
    source_html_sha256: str
    render_snapshot_sha256: str
    rendered_source_pdf_sha256: str
    candidate_pdf_sha256: str


def bind_letter_pdf_candidate(
    *, locked_source: LockedLetterSource, tenant_id: UUID,
    document_id: UUID, document_version: int,
    expected_source_html_sha256: str, source_pdf: bytes,
    expected_render_snapshot_sha256: str,
    candidate_pdf: bytes,
) -> LockedLetterPdfEvidence:
    """Check immutable source IDs and hash the exact provided PDF bytes.

    This does not prove that the source PDF was rendered from the locked HTML:
    the actual issuer must generate and attest the renderer/branding/assets in
    the same secure transaction and re-check after any further signing.
    """
    if (not isinstance(locked_source, LockedLetterSource)
            or not isinstance(tenant_id, UUID)
            or not isinstance(document_id, UUID)
            or locked_source.tenant_id != tenant_id
            or locked_source.document_id != document_id
            or type(document_version) is not int
            or locked_source.version != document_version):
        raise PermissionError("Letter PDF candidate source identity mismatch")
    if (not isinstance(expected_source_html_sha256, str)
            or len(expected_source_html_sha256) != 64
            or not compare_digest(
                locked_source.content_sha256, expected_source_html_sha256,
            )):
        raise PermissionError("Letter PDF candidate source content changed")
    if (not isinstance(expected_render_snapshot_sha256, str)
            or len(expected_render_snapshot_sha256) != 64
            or not compare_digest(
                locked_source.render_snapshot_sha256,
                expected_render_snapshot_sha256,
            )):
        raise PermissionError("Letter rendering snapshot changed")
    source_digest = pdf_fingerprint(source_pdf)
    candidate_digest = pdf_fingerprint(candidate_pdf)
    return LockedLetterPdfEvidence(
        tenant_id=tenant_id, document_id=document_id,
        document_version=document_version,
        source_html_sha256=locked_source.content_sha256,
        render_snapshot_sha256=locked_source.render_snapshot_sha256,
        rendered_source_pdf_sha256=source_digest,
        candidate_pdf_sha256=candidate_digest,
    )
