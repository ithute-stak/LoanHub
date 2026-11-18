"""Exact S3 object version binding to an authorized issuance record."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.document_issuance_immutable_binding import (
    bind_locked_pdf_to_issuance, verify_locked_pdf_for_issuance,
)
from services.document_issuance_immutable_s3 import LockedPdfObject
from services.document_issuance_integrity import pdf_fingerprint
from services.object_storage_service import StorageUnavailableError


PDF = b"%PDF-1.4\nversion-pinned document\n"
PUBLIC_ID = "verified-public-id-12345"


def _fixture():
    tenant = uuid4()
    store = Mock()
    store.bucket = "approved-official-bucket"
    store._key.return_value = f"official/{tenant}/{PUBLIC_ID}.pdf"
    store.read_exact_version.return_value = PDF
    locked = LockedPdfObject(
        bucket=store.bucket,
        key=store._key.return_value,
        version_id="real-version-1",
        sha256_hex=pdf_fingerprint(PDF),
        retain_until=datetime.now(timezone.utc) + timedelta(days=3650),
    )
    issuance = SimpleNamespace(
        company_id=tenant, public_id=PUBLIC_ID, status="issued",
        final_pdf_sha256=pdf_fingerprint(PDF), immutable_bucket=None,
        immutable_object_key=None, immutable_version_id=None,
        immutable_retain_until=None,
    )
    return tenant, store, locked, issuance


def _bind(tenant, store, locked, issuance):
    bind_locked_pdf_to_issuance(
        issuance=issuance, tenant_id=tenant, candidate_pdf=PDF,
        locked=locked, store=store,
    )


def test_immutable_version_and_retention_are_bound_after_exact_read():
    tenant, store, locked, issuance = _fixture()
    _bind(tenant, store, locked, issuance)
    assert issuance.immutable_version_id == "real-version-1"
    assert issuance.immutable_object_key == locked.key
    assert issuance.immutable_retain_until == locked.retain_until
    assert verify_locked_pdf_for_issuance(
        issuance=issuance, tenant_id=tenant, store=store,
    ) == PDF
    assert store.read_exact_version.call_count == 2


def test_cross_tenant_binding_and_verification_denied():
    tenant, store, locked, issuance = _fixture()
    with pytest.raises(PermissionError):
        _bind(uuid4(), store, locked, issuance)
    assert issuance.immutable_version_id is None
    _bind(tenant, store, locked, issuance)
    with pytest.raises(PermissionError):
        verify_locked_pdf_for_issuance(issuance=issuance, tenant_id=uuid4(), store=store)


def test_mismatch_version_bytes_prevents_binding():
    tenant, store, locked, issuance = _fixture()
    store.read_exact_version.return_value = PDF + b"tampered"
    with pytest.raises(StorageUnavailableError):
        _bind(tenant, store, locked, issuance)
    assert issuance.immutable_version_id is None


def test_mismatched_digest_prevents_binding():
    tenant, store, locked, issuance = _fixture()
    issuance.final_pdf_sha256 = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        _bind(tenant, store, locked, issuance)
    assert issuance.immutable_version_id is None


def test_reference_cannot_be_rebound():
    tenant, store, locked, issuance = _fixture()
    _bind(tenant, store, locked, issuance)
    with pytest.raises(ValueError, match="already bound"):
        _bind(tenant, store, locked, issuance)


def test_absent_version_never_uses_mutable_latest_key():
    tenant, store, _, issuance = _fixture()
    with pytest.raises(StorageUnavailableError, match="incomplete"):
        verify_locked_pdf_for_issuance(issuance=issuance, tenant_id=tenant, store=store)
    store.read_exact_version.assert_not_called()


def test_artifact_key_must_match_tenant_and_public_id():
    tenant, store, locked, issuance = _fixture()
    locked = LockedPdfObject(
        bucket=locked.bucket, key="official/another-company/other.pdf",
        version_id=locked.version_id, sha256_hex=locked.sha256_hex,
        retain_until=locked.retain_until,
    )
    with pytest.raises(PermissionError, match="identity"):
        _bind(tenant, store, locked, issuance)


def test_future_retention_required():
    tenant, store, locked, issuance = _fixture()
    locked = LockedPdfObject(
        bucket=locked.bucket, key=locked.key, version_id=locked.version_id,
        sha256_hex=locked.sha256_hex,
        retain_until=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="retention"):
        _bind(tenant, store, locked, issuance)


def test_retention_rechecked_on_binding_and_on_verification():
    tenant, store, locked, issuance = _fixture()
    _bind(tenant, store, locked, issuance)
    store.assert_version_retention.assert_called_once_with(locked)
    verify_locked_pdf_for_issuance(
        issuance=issuance, tenant_id=tenant, store=store,
    )
    assert store.assert_version_retention.call_count == 2
    assert store.assert_version_retention.call_args.args[0].version_id == locked.version_id


def test_provider_retention_failure_denies_new_binding_without_mutation():
    tenant, store, locked, issuance = _fixture()
    store.assert_version_retention.side_effect = StorageUnavailableError("retention not verified")
    with pytest.raises(StorageUnavailableError, match="retention"):
        _bind(tenant, store, locked, issuance)
    assert issuance.immutable_version_id is None
    store.read_exact_version.assert_not_called()


def test_provider_retention_failure_denies_verification_without_fallback():
    tenant, store, locked, issuance = _fixture()
    _bind(tenant, store, locked, issuance)
    store.assert_version_retention.side_effect = StorageUnavailableError("retention expired")
    with pytest.raises(StorageUnavailableError, match="retention"):
        verify_locked_pdf_for_issuance(issuance=issuance, tenant_id=tenant, store=store)
    store.read_exact_version.assert_called_once()
