"""Read-only tenant stamp approval lookup never trusts user supplied evidence."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.document_issuance_stamp_approval_repository import (
    lookup_approved_stamp_from_database,
)
from services.document_issuance_stamp_snapshot import stamp_snapshot_sha256


NOW = datetime.now(timezone.utc)


def _fixture():
    tenant, issuer, approver = uuid4(), uuid4(), uuid4()
    company = SimpleNamespace(
        id=tenant, name="Example Tenant (Pty) Ltd", address="Maseru",
        phone="+266 50000000", email="tenant@example.test",
        registration_number="REG-1", license_number="LIC-1",
    )
    secure = {
        "rls_enabled": True, "runtime_owns_table": False,
        "superuser": False, "bypass_rls": False, "can_select": True,
        "can_insert": False, "can_update": False, "can_delete": False,
        "tenant_policy": True, "actor_scope": "tenant",
        "context_company_id": str(tenant), "context_user_id": str(issuer),
    }
    approval = {
        "company_id": tenant, "configuration_version": 2,
        "snapshot_sha256_hex": stamp_snapshot_sha256(
            company=company, authenticated_tenant_id=tenant,
        ),
        "approved_by_user_id": approver,
        "approved_at": NOW - timedelta(days=1),
        "expires_at": NOW + timedelta(days=1),
        "status": "approved",
    }
    db = Mock()
    db.bind.dialect.name = "postgresql"
    db.execute.side_effect = [
        Mock(mappings=lambda: Mock(one_or_none=lambda: secure)),
        Mock(mappings=lambda: Mock(one_or_none=lambda: approval)),
    ]
    return db, tenant, issuer, company, secure, approval


def _query(db, tenant, issuer, company):
    return lookup_approved_stamp_from_database(
        db=db, company=company, authenticated_tenant_id=tenant,
        issuer_user_id=issuer, configuration_version=2,
    )


def test_protected_database_record_is_accepted_without_mutation():
    db, tenant, issuer, company, _, _ = _fixture()
    result = _query(db, tenant, issuer, company)
    assert result.tenant_id == tenant
    assert result.configuration_version == 2
    assert db.execute.call_count == 2
    db.commit.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.parametrize("change", [
    {"rls_enabled": False}, {"runtime_owns_table": True},
    {"superuser": True}, {"bypass_rls": True},
    {"can_select": False}, {"can_insert": True},
    {"can_update": True}, {"can_delete": True},
    {"tenant_policy": False}, {"actor_scope": "platform"},
    {"context_company_id": "other"}, {"context_user_id": "other"},
])
def test_insecure_db_role_policy_or_context_fails_before_approval_query(change):
    db, tenant, issuer, company, secure, _ = _fixture()
    secure.update(change)
    with pytest.raises(PermissionError, match="SQL security"):
        _query(db, tenant, issuer, company)
    assert db.execute.call_count == 1


def test_missing_approval_registry_fails_closed():
    db, tenant, issuer, company, _, _ = _fixture()
    db.execute.side_effect = [
        Mock(mappings=lambda: Mock(one_or_none=lambda: None)),
    ]
    with pytest.raises(PermissionError, match="SQL security"):
        _query(db, tenant, issuer, company)
    assert db.execute.call_count == 1


def test_missing_approval_record_never_authorizes():
    db, tenant, issuer, company, secure, _ = _fixture()
    db.execute.side_effect = [
        Mock(mappings=lambda: Mock(one_or_none=lambda: secure)),
        Mock(mappings=lambda: Mock(one_or_none=lambda: None)),
    ]
    with pytest.raises(PermissionError, match="No authoritative"):
        _query(db, tenant, issuer, company)


def test_approval_must_be_independent_of_issuer():
    db, tenant, issuer, company, _, approval = _fixture()
    approval["approved_by_user_id"] = issuer
    with pytest.raises(PermissionError, match="Independent"):
        _query(db, tenant, issuer, company)


def test_source_stamp_changed_after_database_approval_is_rejected():
    db, tenant, issuer, company, _, _ = _fixture()
    company.name = "Unapproved Updated Company"
    with pytest.raises(PermissionError, match="approved snapshot"):
        _query(db, tenant, issuer, company)


def test_non_postgres_connection_denied():
    db, tenant, issuer, company, _, _ = _fixture()
    db.bind.dialect.name = "sqlite"
    with pytest.raises(PermissionError, match="PostgreSQL"):
        _query(db, tenant, issuer, company)
    db.execute.assert_not_called()
