"""Non-routed immutable issuance transaction must commit before returning bytes."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from database.models.enums import UserRole
from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore
from services.document_issuance_locked_registration import register_locked_staged_document


PDF = b"%PDF-1.4\nlocked pdf\n"
PUBLIC_ID = "secure-public-id-1234567"


def _fixtures():
    tenant = uuid4()
    context = SimpleNamespace(
        company_id=tenant, company=SimpleNamespace(\n            id=tenant, name="Example Tenant (Pty) Ltd",\n            address="Maseru", phone="+266 50000000",\n            email="tenant@example.test", registration_number="REG-1",\n            license_number="LIC-1",\n        ),
        user=SimpleNamespace(id=uuid4()),
        staff=SimpleNamespace(role=UserRole.COMPANY_ADMIN),
        is_platform_admin=False,
    )
    store = object.__new__(S3ObjectLockPdfStore)
    store.bucket = "approved-locked-bucket"
    candidate = SimpleNamespace(
        tenant_id=tenant, public_id=PUBLIC_ID,
        pdf_bytes=PDF,
        sha256_hex=__import__("hashlib").sha256(PDF).hexdigest(),
    )
    locked = SimpleNamespace(version_id="v-locked-1")
    staged = SimpleNamespace(
        candidate=candidate, locked=locked,
        source_sha256_hex=__import__("hashlib").sha256(PDF).hexdigest(),
    )
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    return db, context, store, staged


def _register(db, context, store, staged):
    return register_locked_staged_document(
        db=db, context=context, staged=staged, store=store,
        source_pdf=PDF, source_type="workspace", source_id="doc-001",
        document_type="agreement", idempotency_key="request-001",
        version=1, stamp_configuration_version=1,
    )


@pytest.fixture(autouse=True)
def _mock_db_gate():
    with patch("services.document_issuance_locked_registration.require_document_issuance_database_ready"):
        yield


def test_issuance_commits_with_audit_before_returning_document():
    db, context, store, staged = _fixtures()
    def flush():
        for call in db.add.call_args_list:
            record = call.args[0]
            if type(record).__name__ == "DocumentIssuance":
                record.id = uuid4()
    db.flush.side_effect = flush
    with patch("services.document_issuance_locked_registration.bind_locked_pdf_to_issuance") as binder:
        result = _register(db, context, store, staged)
    binder.assert_called_once()
    assert result.document_bytes == PDF
    assert result.immutable_version_id == "v-locked-1"
    assert db.add.call_count == 2
    assert db.flush.call_count == 2
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_uncertain_commit_fails_and_never_returns_document():
    db, context, store, staged = _fixtures()
    db.commit.side_effect = RuntimeError("commit state unknown")
    with patch("services.document_issuance_locked_registration.bind_locked_pdf_to_issuance"):
        with pytest.raises(RuntimeError, match="state unknown"):
            _register(db, context, store, staged)
    db.rollback.assert_called_once()
    # Object deletion is intentionally not attempted.


def test_prior_issuance_does_not_create_new_audit_or_release_pdf():
    db, context, store, staged = _fixtures()
    db.query.return_value.filter.return_value.one_or_none.return_value = object()
    with pytest.raises(ValueError, match="already registered"):
        _register(db, context, store, staged)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_cross_company_candidate_denied_before_database_writes():
    db, context, store, staged = _fixtures()
    staged.candidate.tenant_id = uuid4()
    with pytest.raises(PermissionError, match="another tenant"):
        _register(db, context, store, staged)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_invalid_candidate_hash_denied_before_database_writes():
    db, context, store, staged = _fixtures()
    staged.candidate.sha256_hex = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        _register(db, context, store, staged)
    db.add.assert_not_called()


def test_binder_failure_rolls_back_without_releasing_document():
    db, context, store, staged = _fixtures()
    with patch("services.document_issuance_locked_registration.bind_locked_pdf_to_issuance",
               side_effect=PermissionError("wrong locked version")):
        with pytest.raises(PermissionError, match="wrong locked version"):
            _register(db, context, store, staged)
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_database_readiness_denial_prevents_registration():
    db, context, store, staged = _fixtures()
    with patch("services.document_issuance_locked_registration.require_document_issuance_database_ready",
               side_effect=PermissionError("unsafe role")):
        with pytest.raises(PermissionError, match="unsafe role"):
            _register(db, context, store, staged)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_mutable_adapter_denied():
    db, context, _, staged = _fixtures()
    with pytest.raises(PermissionError, match="Object Lock"):
        _register(db, context, SimpleNamespace(provider="s3"), staged)
    db.commit.assert_not_called()


def test_source_pdf_changed_after_scanning_is_rejected_before_db_access():
    db, context, store, staged = _fixtures()
    staged.source_sha256_hex = "0" * 64
    with pytest.raises(ValueError, match="originally scanned"):
        _register(db, context, store, staged)
    db.query.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_company_stamp_changes_between_staging_and_registration_rejected():
    db, context, store, staged = _fixtures()
    context.company.name = "Unexpected Replacement Company"
    with pytest.raises(ValueError, match="Company stamp fields changed"):
        _register(db, context, store, staged)
    db.query.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
