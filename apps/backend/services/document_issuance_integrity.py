"""Pure issuance integrity primitives; no persistence or verification endpoint.

Security boundary: a displayed QR is not proof. Always require an authoritative
tenant-scoped issuance record and compare SHA-256 of the *exact final PDF bytes*.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class IssuanceFingerprint:
    tenant_id: UUID
    public_id: str
    sha256_hex: str
    status: str


def new_public_document_id() -> str:
    """Non-sequential, unguessable locator; not an authorization token."""
    return secrets.token_urlsafe(24)


def pdf_fingerprint(pdf: bytes) -> str:
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-") or len(pdf) > 25 * 1024 * 1024:
        raise ValueError("Invalid finalized PDF")
    return hashlib.sha256(pdf).hexdigest()


def verify_exact_document(
    *, pdf: bytes, record: IssuanceFingerprint | None,
    expected_tenant_id: UUID, requested_public_id: str,
) -> str:
    """Return exact-file verification state, without leaking other tenant data.

    Caller must fetch the record from a trusted database; never construct it
    from untrusted HTTP request body. No status can be 'verified' absent file
    bytes and a matching issued record.
    """
    if record is None or record.tenant_id != expected_tenant_id or record.public_id != requested_public_id:
        return "not_found"
    if record.status == "revoked":
        return "revoked"
    if record.status == "superseded":
        return "superseded"
    if record.status != "issued":
        return "unverified"
    digest = pdf_fingerprint(pdf)
    if not isinstance(record.sha256_hex, str) or len(record.sha256_hex) != 64:
        return "unverified"
    return "verified" if hmac.compare_digest(digest, record.sha256_hex) else "altered"
