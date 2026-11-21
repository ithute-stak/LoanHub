"""Company stamp approval contract: independent, tenant-specific, versioned."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.document_issuance_stamp_approval import (
    ApprovedCompanyStamp, require_approved_company_stamp_snapshot,
)
from services.document_issuance_stamp_snapshot import stamp_snapshot_sha256


NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def _fixture():
    tenant, issuer, approver = uuid4(), uuid4(), uuid4()
    company = SimpleNamespace(
        id=tenant, name="Example Tenant (Pty) Ltd",
        address="Maseru", phone="+266 50000000",
        email="tenant@example.test",
        registration_number="REG-001", license_number="LIC-001",
    )
    approval = ApprovedCompanyStamp(
        tenant_id=tenant, configuration_version=2,
        snapshot_sha256_hex=stamp_snapshot_sha256(
            company=company, authenticated_tenant_id=tenant,
        ),
        approved_by_user_id=approver,
        approved_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=30),
        status="approved",
    )
    return tenant, issuer, company, approval


def _check(tenant, issuer, company, approval):
    return require_approved_company_stamp_snapshot(
        company=company, authenticated_tenant_id=tenant,
        issuer_user_id=issuer, approval=approval,
        configuration_version=2, now=NOW,
    )


def test_matching_independently_approved_stamp_passes():
    tenant, issuer, company, approval = _fixture()
    assert _check(tenant, issuer, company, approval) == approval.snapshot_sha256_hex


@pytest.mark.parametrize("change", [
    {"status": "pending"}, {"status": "revoked"},
    {"configuration_version": 1}, {"tenant_id": uuid4()},
    {"snapshot_sha256_hex": "0" * 64},
    {"approved_at": NOW + timedelta(days=1)},
    {"expires_at": NOW - timedelta(seconds=1)},
    {"expires_at": NOW - timedelta(days=2)},
])
def test_invalid_approval_fails_closed(change):
    tenant, issuer, company, approval = _fixture()
    with pytest.raises(PermissionError):
        _check(tenant, issuer, company, replace(approval, **change))


def test_issuer_cannot_approve_own_stamp():
    tenant, issuer, company, approval = _fixture()
    with pytest.raises(PermissionError, match="Independent"):
        _check(tenant, issuer, company, replace(approval, approved_by_user_id=issuer))


def test_company_detail_modified_since_approval_rejected():
    tenant, issuer, company, approval = _fixture()
    company.name = "Changed Legal Company"
    with pytest.raises(PermissionError, match="approved snapshot"):
        _check(tenant, issuer, company, approval)


def test_missing_authoritative_approval_never_authorizes():
    tenant, issuer, company, _ = _fixture()
    with pytest.raises(PermissionError, match="approval required"):
        _check(tenant, issuer, company, None)


def test_unverified_tenant_is_rejected():
    tenant, issuer, company, approval = _fixture()
    with pytest.raises(PermissionError, match="another tenant"):
        _check(uuid4(), issuer, company, approval)
