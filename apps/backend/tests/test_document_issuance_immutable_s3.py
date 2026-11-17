"""Mocked S3 Object Lock contract. Real storage certification remains pending."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from unittest.mock import Mock

import pytest

from services.document_issuance_immutable_s3 import (
    LockedPdfObject, S3ObjectLockPdfStore,
)
from services.object_storage_service import StorageUnavailableError


PDF = b"%PDF-1.4\nlocked exact bytes\n"


def _store():
    client = Mock()
    client.get_bucket_versioning.return_value = {"Status": "Enabled"}
    client.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}
    }
    client.put_object.return_value = {"VersionId": "version-123"}
    client.get_object_retention.return_value = {
        "Retention": {
            "Mode": "COMPLIANCE",
            "RetainUntilDate": datetime.now(timezone.utc) + timedelta(days=3700),
        }
    }
    client.get_object.return_value = {"Body": BytesIO(PDF)}
    return S3ObjectLockPdfStore(client=client, bucket="test-locked-bucket"), client


def test_upload_proves_compliance_mode_and_reads_exact_version():
    store, client = _store()
    record = store.put_locked_pdf(
        tenant_id="tenant-a", public_id="verified-public-id-123", pdf=PDF
    )
    assert record.version_id == "version-123"
    assert record.sha256_hex == sha256(PDF).hexdigest()
    assert client.put_object.call_args.kwargs["ObjectLockMode"] == "COMPLIANCE"
    assert client.get_object_retention.call_args.kwargs["VersionId"] == "version-123"
    assert store.read_exact_version(record) == PDF
    assert client.get_object.call_args.kwargs["VersionId"] == "version-123"


@pytest.mark.parametrize("versioning,lock", [
    ("Suspended", "Enabled"), ("Enabled", None), (None, "Enabled"),
])
def test_bucket_must_prove_object_lock_and_active_versioning(versioning, lock):
    store, client = _store()
    client.get_bucket_versioning.return_value = {"Status": versioning}
    client.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {"ObjectLockEnabled": lock}
    }
    with pytest.raises(StorageUnavailableError):
        store.put_locked_pdf(tenant_id="tenant-a", public_id="verified-public-id-123", pdf=PDF)
    client.put_object.assert_not_called()


@pytest.mark.parametrize("version", [None, "", "null"])
def test_missing_version_id_fails_closed(version):
    store, client = _store()
    client.put_object.return_value = {"VersionId": version}
    with pytest.raises(StorageUnavailableError, match="version ID"):
        store.put_locked_pdf(tenant_id="tenant-a", public_id="verified-public-id-123", pdf=PDF)


def test_noncompliant_retention_fails_closed():
    store, client = _store()
    client.get_object_retention.return_value = {
        "Retention": {
            "Mode": "GOVERNANCE",
            "RetainUntilDate": datetime.now(timezone.utc) + timedelta(days=3700),
        }
    }
    with pytest.raises(StorageUnavailableError, match="retention"):
        store.put_locked_pdf(tenant_id="tenant-a", public_id="verified-public-id-123", pdf=PDF)


def test_corrupted_exact_version_is_rejected():
    store, client = _store()
    record = store.put_locked_pdf(
        tenant_id="tenant-a", public_id="verified-public-id-123", pdf=PDF
    )
    client.get_object.return_value = {"Body": BytesIO(PDF + b"changed")}
    with pytest.raises(StorageUnavailableError, match="fingerprint"):
        store.read_exact_version(record)


def test_other_bucket_cannot_read_immutable_reference():
    store, client = _store()
    record = LockedPdfObject(
        bucket="another-bucket", key="no", version_id="v1",
        sha256_hex="a"*64, retain_until=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError, match="bucket"):
        store.read_exact_version(record)
    client.get_object.assert_not_called()
