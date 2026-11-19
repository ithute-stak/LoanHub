"""Never auto-delete or reissue locked objects during commit recovery."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from services.document_issuance_immutable_s3 import LockedPdfObject, S3ObjectLockPdfStore
from services.document_issuance_reconciliation import assess_locked_issuance_recovery
from services.object_storage_service import StorageUnavailableError


PDF = b"%PDF-1.4\noriginal immutable bytes\n"
PUBLIC_ID = "locked-recovery-123456789"


def _fixtures():
    company = uuid4()
    store = object.__new__(S3ObjectLockPdfStore)
    store.bucket = "official-bucket"
    store.prefix = "official-issuances"
    store.read_exact_version = Mock(return_value=PDF)
    store.assert_version_retention = Mock()
    locked = LockedPdfObject(
        bucket=store.bucket,
        key=store._key(str(company), PUBLIC_ID),
        version_id="immutable-version-123",
        sha256_hex=sha256(PDF).hexdigest(),
        retain_until=datetime.now(timezone.utc) + timedelta(days=3650),
    )
    record = SimpleNamespace(
        company_id=company, public_id=PUBLIC_ID, status="issued",
        immutable_bucket=locked.bucket, immutable_object_key=locked.key,
        immutable_version_id=locked.version_id,
        final_pdf_sha256=locked.sha256_hex,
    )
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = record
    return company, store, locked, db, record


def _assess(company, store, locked, db):
    return assess_locked_issuance_recovery(
        db=db, authenticated_tenant_id=company,
        public_id=PUBLIC_ID, locked=locked, store=store,
    )


@pytest.fixture(autouse=True)
def _allow_restricted_role_for_unit_tests():
    with patch("services.document_issuance_reconciliation.require_document_issuance_database_ready"):
        yield


def test_committed_locked_version_can_be_verified_without_mutation():
    company, store, locked, db, _ = _fixtures()
    result = _assess(company, store, locked, db)
    assert result.status == "registered_version_verified"
    assert not result.manual_review_required
    store.assert_version_retention.assert_called_once_with(locked)
    db.commit.assert_not_called()
    db.add.assert_not_called()


def test_unregistered_locked_object_is_retained_for_review():
    company, store, locked, db, _ = _fixtures()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    result = _assess(company, store, locked, db)
    assert result.status == "unregistered_locked_object_review"
    assert result.manual_review_required
    store.read_exact_version.assert_not_called()
    store.assert_version_retention.assert_not_called()
    db.commit.assert_not_called()


def test_mismatched_registered_version_requires_review():
    company, store, locked, db, record = _fixtures()
    record.immutable_version_id = "other-version"
    result = _assess(company, store, locked, db)
    assert result.status == "registered_reference_mismatch"
    assert result.manual_review_required
    store.read_exact_version.assert_not_called()


def test_modified_canonical_bytes_are_not_verified():
    company, store, locked, db, _ = _fixtures()
    store.read_exact_version.return_value = PDF + b"changed"
    result = _assess(company, store, locked, db)
    assert result.status == "registered_digest_mismatch"
    assert result.manual_review_required


def test_missing_provider_version_is_not_verified():
    company, store, locked, db, _ = _fixtures()
    store.read_exact_version.side_effect = StorageUnavailableError("version missing")
    result = _assess(company, store, locked, db)
    assert result.status == "locked_version_unavailable"
    assert result.manual_review_required


def test_revoked_issuance_is_not_reported_as_verified():
    company, store, locked, db, record = _fixtures()
    record.status = "revoked"
    result = _assess(company, store, locked, db)
    assert result.status == "registered_inactive"
    store.read_exact_version.assert_not_called()


def test_cross_tenant_recovery_is_rejected_before_sql():
    company, store, locked, db, _ = _fixtures()
    with pytest.raises(PermissionError, match="identity mismatch"):
        _assess(uuid4(), store, locked, db)
    db.query.assert_not_called()


def test_unsafe_database_role_prevents_recovery_assessment():
    company, store, locked, db, _ = _fixtures()
    with patch("services.document_issuance_reconciliation.require_document_issuance_database_ready",
               side_effect=PermissionError("RLS not ready")):
        with pytest.raises(PermissionError, match="RLS not ready"):
            _assess(company, store, locked, db)
    db.query.assert_not_called()


def test_provider_retention_expired_requires_review_without_reading_pdf():
    company, store, locked, db, _ = _fixtures()
    store.assert_version_retention.side_effect = StorageUnavailableError(
        "Exact PDF version lacks valid COMPLIANCE retention"
    )
    result = _assess(company, store, locked, db)
    assert result.status == "locked_version_unavailable"
    assert result.manual_review_required
    store.assert_version_retention.assert_called_once_with(locked)
    store.read_exact_version.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_provider_retention_inspection_failure_requires_manual_review():
    company, store, locked, db, _ = _fixtures()
    store.assert_version_retention.side_effect = StorageUnavailableError(
        "Cannot inspect exact PDF version retention"
    )
    result = _assess(company, store, locked, db)
    assert result.status == "locked_version_unavailable"
    assert result.manual_review_required
    store.read_exact_version.assert_not_called()


def test_inactive_issuance_never_probes_provider_retention():
    company, store, locked, db, record = _fixtures()
    record.status = "revoked"
    result = _assess(company, store, locked, db)
    assert result.status == "registered_inactive"
    store.assert_version_retention.assert_not_called()
    store.read_exact_version.assert_not_called()
