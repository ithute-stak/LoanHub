"""The official stamp preflight remains read-only and never renders a document."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from core.access_control import TenantContext
from database.models.enums import UserRole

import pytest

from services.document_studio_letter_stamp_authorization import (
    preflight_approved_letter_stamp,
)
from services.document_issuance_stamp_snapshot import stamp_snapshot_sha256


@pytest.fixture(autouse=True)
def isolated_trusted_issuer_gate():
    # Approval tests exercise downstream behavior on an already trusted DB
    # login. Dedicated gate failure is verified separately below.
    with patch(
        "services.document_studio_letter_stamp_authorization.require_trusted_issuer_database_login",
    ), patch(
        "services.document_studio_letter_stamp_authorization.require_current_document_issuer",
        side_effect=lambda *, db, context: SimpleNamespace(
            user_id=context.user.id, company_id=context.company_id,
        ),
    ), patch(
        "services.document_studio_letter_stamp_authorization.read_issuer_transaction_identity",
        return_value=SimpleNamespace(backend_pid=123, transaction_id="1"),
    ), patch(
        "services.document_studio_letter_stamp_authorization.require_same_issuer_transaction",
    ):
        yield


def fixture():
    tenant, issuer, approver = uuid4(), uuid4(), uuid4()
    company = SimpleNamespace(
        id=tenant, name="Example Finance", address="Maseru",
        phone="+266 50000000", email="team@example.test",
        registration_number="REG-001", license_number="LIC-001",
    )
    document = SimpleNamespace(
        company_id=tenant, template_key="formal_letter",
        status="draft", finalized_at=None,
    )
    approval = SimpleNamespace(
        tenant_id=tenant, configuration_version=3,
        approved_by_user_id=approver,
        snapshot_sha256_hex=stamp_snapshot_sha256(
            company=company, authenticated_tenant_id=tenant,
        ),
    )
    return tenant, issuer, approver, company, document, approval


def check(db, tenant, issuer, company, document):
    context = TenantContext(
        user=SimpleNamespace(id=issuer),
        staff=SimpleNamespace(
            id=uuid4(), user_id=issuer, company_id=tenant,
            role=UserRole.COMPANY_ADMIN, is_active=True,
        ),
        company=company, company_id=tenant,
        branch_id=None, is_platform_admin=False,
    )
    return preflight_approved_letter_stamp(
        db=db, context=context, document=document, company=company,
        authenticated_tenant_id=tenant, issuer_user_id=issuer,
        configuration_version=3,
    )


def test_authoritative_gate_returns_immutable_identity_without_writing():
    tenant, issuer, approver, company, document, approval = fixture()
    db = Mock()
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ) as lookup:
        result = check(db, tenant, issuer, company, document)
    assert result.tenant_id == tenant
    assert result.approved_by_user_id == approver
    assert result.configuration_version == 3
    assert result.stamp_snapshot_sha256 == approval.snapshot_sha256_hex
    lookup.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.flush.assert_not_called()


@pytest.mark.parametrize("change", [
    ("company_id", uuid4()), ("company_id", None),
    ("template_key", "contract"), ("template_key", "invoice"),
    ("status", "published"), ("status", "finalized"),
    ("finalized_at", datetime(2026, 11, 21, tzinfo=timezone.utc)),
])
def test_disallowed_document_rejected_before_sql(change):
    tenant, issuer, _, company, document, approval = fixture()
    setattr(document, change[0], change[1])
    db = Mock()
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ) as lookup, pytest.raises(PermissionError):
        check(db, tenant, issuer, company, document)
    lookup.assert_not_called()


def test_cross_tenant_company_rejected_before_sql():
    tenant, issuer, _, company, document, approval = fixture()
    company.id = uuid4()
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ) as lookup, pytest.raises(PermissionError, match="Authenticated company staff context required"):
        check(Mock(), tenant, issuer, company, document)
    lookup.assert_not_called()


@pytest.mark.parametrize("issuer", [None, "unverified-user"])
def test_unverified_issuer_fails_without_accessing_database(issuer):
    tenant, _, _, company, document, approval = fixture()
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ) as lookup, pytest.raises(PermissionError, match="Verified"):
        check(Mock(), tenant, issuer, company, document)
    lookup.assert_not_called()


def test_missing_approval_cannot_be_substituted_with_request_data():
    tenant, issuer, _, company, document, _ = fixture()
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        side_effect=PermissionError("No authoritative stamp approval"),
    ), pytest.raises(PermissionError, match="authoritative"):
        check(Mock(), tenant, issuer, company, document)


def test_company_mutation_after_approval_read_is_rejected():
    tenant, issuer, _, company, document, approval = fixture()
    def mutate_company(**kwargs):
        company.name = "A Different Company"
        return approval
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        side_effect=mutate_company,
    ), pytest.raises(PermissionError, match="changed during authorization"):
        check(Mock(), tenant, issuer, company, document)


def test_signed_document_rejected_before_approval_query():
    tenant, issuer, _, company, document, approval = fixture()
    document.signatures = [SimpleNamespace(revoked_at=None)]
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ) as lookup, pytest.raises(PermissionError, match="Signed letters"):
        check(Mock(), tenant, issuer, company, document)
    lookup.assert_not_called()


def test_untrusted_database_login_rejected_before_stamp_approval_lookup():
    tenant, issuer, _, company, document, approval = fixture()
    with patch(
        "services.document_studio_letter_stamp_authorization.require_trusted_issuer_database_login",
        side_effect=PermissionError("Untrusted document issuer database login"),
    ) as trusted, patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ) as lookup, pytest.raises(PermissionError, match="Untrusted"):
        check(Mock(), tenant, issuer, company, document)
    trusted.assert_called_once()
    lookup.assert_not_called()


def test_approval_lookup_occurs_only_after_trusted_login_gate():
    tenant, issuer, _, company, document, approval = fixture()
    order = []
    def trusted_db(**kwargs):
        order.append("trusted-login")
    def lookup_approval(**kwargs):
        order.append("approval")
        return approval
    with patch(
        "services.document_studio_letter_stamp_authorization.require_trusted_issuer_database_login",
        side_effect=trusted_db,
    ), patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        side_effect=lookup_approval,
    ):
        check(Mock(), tenant, issuer, company, document)
    assert order == ["trusted-login", "approval"]


def test_revoked_current_staff_denies_approval_lookup():
    tenant, issuer, _, company, document, approval = fixture()
    with patch(
        "services.document_studio_letter_stamp_authorization.require_current_document_issuer",
        side_effect=PermissionError("Issuer membership revoked"),
    ) as issuer_gate, patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ) as approval_lookup, pytest.raises(PermissionError, match="revoked"):
        check(Mock(), tenant, issuer, company, document)
    issuer_gate.assert_called_once()
    approval_lookup.assert_not_called()


def test_transaction_replaced_during_stamp_approval_is_rejected():
    tenant, issuer, _, company, document, approval = fixture()
    db = Mock()
    transaction_before = object()
    transaction_after = object()
    db.get_transaction.side_effect = [transaction_before, transaction_after]
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ), pytest.raises(PermissionError, match="transaction was replaced"):
        check(db, tenant, issuer, company, document)
    db.commit.assert_not_called()


def test_postgres_transaction_switch_after_stamp_lookup_denied():
    tenant, issuer, _, company, document, approval = fixture()
    with patch(
        "services.document_studio_letter_stamp_authorization.lookup_approved_stamp_from_database",
        return_value=approval,
    ), patch(
        "services.document_studio_letter_stamp_authorization.require_same_issuer_transaction",
        side_effect=PermissionError("PostgreSQL issuer transaction changed"),
    ), pytest.raises(PermissionError, match="transaction changed"):
        check(Mock(), tenant, issuer, company, document)
