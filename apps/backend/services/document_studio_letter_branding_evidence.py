"""Non-routed evidence of actual visual branding inputs for a letter PDF.

Captures the exact bytes and company identity a trusted renderer must use.
Does not approve a company stamp or prove a finished PDF was rendered from
these bytes. Do not use to certify a PDF produced in a separate transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from json import dumps
from uuid import UUID


@dataclass(frozen=True)
class LetterBrandingEvidence:
    tenant_id: UUID
    identity_sha256: str
    left_logo_sha256: str | None
    right_logo_sha256: str | None
    combined_sha256: str


def capture_letter_branding_evidence(
    *, document, company, left_logo: bytes | None, right_logo: bytes | None,
) -> LetterBrandingEvidence:
    tenant_id = getattr(document, "company_id", None)
    if (not isinstance(tenant_id, UUID) or company is None
            or getattr(company, "id", None) != tenant_id):
        raise PermissionError("Letter branding belongs to another tenant")
    fields = ("name", "registration_number", "license_number", "phone",
              "email", "website", "address", "district")
    identity = {}
    for field in fields:
        value = getattr(company, field, None)
        if value is not None and not isinstance(value, str):
            raise PermissionError("Invalid legal identity field for letter branding")
        identity[field] = value
    if not identity["name"]:
        raise PermissionError("Company legal identity is required")
    for item in (left_logo, right_logo):
        if item is not None and (not isinstance(item, bytes) or not item):
            raise PermissionError("Invalid resolved company branding image")
    left_digest = sha256(left_logo).hexdigest() if left_logo is not None else None
    right_digest = sha256(right_logo).hexdigest() if right_logo is not None else None
    identity_digest = sha256(dumps(identity, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False).encode("utf-8")).hexdigest()
    full = {
        "tenant_id": str(tenant_id), "identity_sha256": identity_digest,
        "left_logo_sha256": left_digest, "right_logo_sha256": right_digest,
    }
    return LetterBrandingEvidence(
        tenant_id=tenant_id, identity_sha256=identity_digest,
        left_logo_sha256=left_digest, right_logo_sha256=right_digest,
        combined_sha256=sha256(dumps(full, sort_keys=True, separators=(",", ":"))
                                .encode("utf-8")).hexdigest(),
    )
