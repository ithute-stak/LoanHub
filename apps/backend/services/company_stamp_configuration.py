"""Resolve official document stamp fields from the authenticated tenant.

This intentionally does not seed or overwrite company configuration. An
administrator must review the approved company details before issuance.
"""
from __future__ import annotations

from uuid import UUID

from services.document_stamp_certificate import TenantStamp


def stamp_from_company(company, *, authenticated_tenant_id: UUID) -> TenantStamp:
    """Fail closed if a different tenant's record or incomplete data is supplied."""
    if company is None or getattr(company, "id", None) != authenticated_tenant_id:
        raise PermissionError("Company configuration does not match active tenant")
    stamp = TenantStamp(
        tenant_id=authenticated_tenant_id,
        legal_name=str(getattr(company, "legal_name", None) or getattr(company, "name", "") or "").strip(),
        address=str(getattr(company, "address", "") or "").strip(),
        phones=str(getattr(company, "phone", "") or "").strip(),
        email=str(getattr(company, "email", "") or "").strip(),
        registration_number=str(getattr(company, "registration_number", "") or "").strip(),
        license_number=str(getattr(company, "license_number", "") or "").strip(),
    )
    stamp.validate()
    return stamp
