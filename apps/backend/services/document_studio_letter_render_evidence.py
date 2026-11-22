"""Non-routed adapter that binds the *same* PDF render to actual logo bytes.

This prepares evidence only. It never authorizes or issues an official PDF.
A separately trusted issuer must own the transaction, approval, immutable
object registration and audit record.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from uuid import UUID

from services.document_issuance_integrity import pdf_fingerprint
from services.document_studio_letter_branding_evidence import LetterBrandingEvidence
from services.document_studio_letter_stamp_authorization import LETTER_TEMPLATES
from services.workspace_document_service import export_pdf


@dataclass(frozen=True)
class RenderedLetterCandidate:
    tenant_id: UUID
    pdf_bytes: bytes
    pdf_sha256: str
    header_branding: LetterBrandingEvidence


def render_letter_pdf_with_header_evidence(
    *, db, document, company, authenticated_tenant_id: UUID,
) -> RenderedLetterCandidate:
    """Capture exact header logo inputs during one letter export.

    The trusted caller MUST separately attest the persisted source version,
    external cover-page artwork, fonts and renderer, signature state and
    final issuer's transaction continuity. This is not an issuance API.
    """
    if (not isinstance(authenticated_tenant_id, UUID)
            or getattr(document, "company_id", None) != authenticated_tenant_id
            or company is None or getattr(company, "id", None) != authenticated_tenant_id):
        raise PermissionError("Letter PDF rendering tenant mismatch")
    if (getattr(document, "template_key", None) not in LETTER_TEMPLATES
            or getattr(document, "status", None) != "draft"
            or getattr(document, "finalized_at", None) is not None):
        raise PermissionError("Official evidence requires a draft company letter")
    if os.getenv("LOANHUB_LETTER_STAMP_PREVIEW_ENABLED") == "1":
        raise PermissionError("Preview-marked PDFs cannot be official issuance candidates")
    branding = []
    pdf = export_pdf(
        db, document, company, _branding_evidence_out=branding,
    )
    if len(branding) != 1 or not isinstance(branding[0], LetterBrandingEvidence):
        raise PermissionError("Renderer did not supply exact branding evidence")
    return RenderedLetterCandidate(
        tenant_id=authenticated_tenant_id,
        pdf_bytes=pdf,
        pdf_sha256=pdf_fingerprint(pdf),
        header_branding=branding[0],
    )
