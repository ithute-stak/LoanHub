"""Prepare an unissued, tenant-bound official PDF candidate.

This is deliberately not the issuance API. Caller must persist the *exact*
returned bytes to protected private storage, register them in the same
authorized tenant-scoped transaction, and only then release them to users.

Never infer 'issued' from this return value. QR contents are just a locator.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from services.company_stamp_configuration import stamp_from_company
from services.document_stamp_certificate import render_tenant_stamp_certificate
from services.document_issuance_integrity import (
    new_public_document_id, pdf_fingerprint,
)


@dataclass(frozen=True)
class PreparedDocumentCandidate:
    public_id: str
    pdf_bytes: bytes
    sha256_hex: str
    tenant_id: UUID
    verification_url: str


def prepare_stamped_document_candidate(
    *, source_pdf: bytes, company, authenticated_tenant_id: UUID,
    issued_at: datetime, trusted_verification_origin: str,
    public_id: str | None = None,
) -> PreparedDocumentCandidate:
    """Build issuer certificate, QR, and exact candidate digest together.

    All inputs are supplied by trusted backend code, *never* client identity
    headers; intended as a step toward one canonical PDF finalization path.
    The company's actual approval and feature flag must be checked upstream.
    """
    stamp = stamp_from_company(company, authenticated_tenant_id=authenticated_tenant_id)
    origin = trusted_verification_origin
    if not isinstance(origin, str):
        raise ValueError("Trusted verification origin is required")
    parsed = urlparse(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or parsed.params):
        raise ValueError("Verification origin must be a trusted HTTPS origin")
    # No unverified document IDs are injected from request body or URL params.
    identity = public_id if public_id is not None else new_public_document_id()
    url = f"{origin.rstrip('/')}/verify/{identity}"
    marked_pdf = render_tenant_stamp_certificate(
        source_pdf=source_pdf,
        stamp=stamp,
        public_id=identity,
        verification_url=url,
        issued_at=issued_at,
        expected_tenant_id=authenticated_tenant_id,
        trusted_verification_host=parsed.netloc,
    )
    return PreparedDocumentCandidate(
        public_id=identity,
        pdf_bytes=marked_pdf,
        sha256_hex=pdf_fingerprint(marked_pdf),
        tenant_id=authenticated_tenant_id,
        verification_url=url,
    )
