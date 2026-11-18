"""Deterministic tenant stamp snapshot fingerprint for a non-routed issuance.

This proves that the company fields used at staging remain unchanged at SQL
registration. It does NOT prove a stamp version was formally approved.
"""
from __future__ import annotations

from hashlib import sha256
from json import dumps
from uuid import UUID

from services.company_stamp_configuration import stamp_from_company


STAMP_FIELDS = (
    "tenant_id", "legal_name", "address", "phones", "email",
    "registration_number", "license_number",
)


def stamp_snapshot_sha256(*, company, authenticated_tenant_id: UUID) -> str:
    stamp = stamp_from_company(
        company, authenticated_tenant_id=authenticated_tenant_id,
    )
    canonical = {
        name: str(getattr(stamp, name))
        for name in STAMP_FIELDS
    }
    return sha256(dumps(
        canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
