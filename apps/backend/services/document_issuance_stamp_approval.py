"""Non-routed approval evidence validator for official company stamps.

This intentionally DOES NOT approve anything or load approval evidence from
untrusted request data. A future caller must query an authoritative,
tenant-isolated, append-audited approval registry using a restricted SQL role.
A passing check means the supplied approval snapshot is internally consistent;
it is not proof of database provenance until that integration exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hmac import compare_digest
from uuid import UUID

from services.document_issuance_stamp_snapshot import stamp_snapshot_sha256


@dataclass(frozen=True, slots=True)
class ApprovedCompanyStamp:
    tenant_id: UUID
    configuration_version: int
    snapshot_sha256_hex: str
    approved_by_user_id: UUID
    approved_at: datetime
    expires_at: datetime | None
    status: str


def require_approved_company_stamp_snapshot(
    *, company, authenticated_tenant_id: UUID,
    approval: ApprovedCompanyStamp, issuer_user_id: UUID,
    configuration_version: int, now: datetime | None = None,
) -> str:
    """Validate a separately approved exact snapshot; fail closed.

    Caller MUST fetch approval via a trusted tenant-scoped DB query, not
    from request JSON or a company object. A preparer/issuer may not be
    the approver. Pending/revoked/expired approvals never authorize issuance.
    """
    if not isinstance(authenticated_tenant_id, UUID) or not isinstance(issuer_user_id, UUID):
        raise PermissionError("Verified tenant and issuing actor required")
    if not isinstance(approval, ApprovedCompanyStamp):
        raise PermissionError("Authoritative company stamp approval required")
    if approval.tenant_id != authenticated_tenant_id:
        raise PermissionError("Company stamp approval belongs to another tenant")
    if (type(configuration_version) is not int or configuration_version < 1
            or type(approval.configuration_version) is not int
            or approval.configuration_version != configuration_version):
        raise PermissionError("Company stamp approval version does not match issuance")
    if approval.status != "approved":
        raise PermissionError("Company stamp approval is not active")
    if (not isinstance(approval.approved_by_user_id, UUID)
            or approval.approved_by_user_id == issuer_user_id):
        raise PermissionError("Independent company stamp approval required")
    current = datetime.now(timezone.utc) if now is None else now
    if (not isinstance(current, datetime) or current.tzinfo is None
            or not isinstance(approval.approved_at, datetime)
            or approval.approved_at.tzinfo is None
            or approval.approved_at > current):
        raise PermissionError("Company stamp approval timestamp is invalid")
    if approval.expires_at is not None and (
        not isinstance(approval.expires_at, datetime)
        or approval.expires_at.tzinfo is None
        or approval.expires_at <= current
        or approval.expires_at <= approval.approved_at
    ):
        raise PermissionError("Company stamp approval has expired or is invalid")
    digest = stamp_snapshot_sha256(
        company=company, authenticated_tenant_id=authenticated_tenant_id,
    )
    if (not isinstance(approval.snapshot_sha256_hex, str)
            or len(approval.snapshot_sha256_hex) != 64
            or not compare_digest(approval.snapshot_sha256_hex, digest)):
        raise PermissionError("Company stamp differs from approved snapshot")
    return digest
