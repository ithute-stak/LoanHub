"""Read-only S3 bucket checks reject missing security assurances."""
from unittest.mock import Mock

import pytest

from services.document_issuance_bucket_preflight import inspect_locked_bucket_read_only


def _secure_client():
    client = Mock()
    client.get_bucket_versioning.return_value = {"Status": "Enabled"}
    client.get_object_lock_configuration.return_value = {
        "ObjectLockConfiguration": {
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Years": 10}},
        }
    }
    client.get_public_access_block.return_value = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
    }
    client.get_bucket_encryption.return_value = {
        "ServerSideEncryptionConfiguration": {
            "Rules": [
                {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
            ]
        }
    }
    client.get_bucket_policy_status.return_value = {
        "PolicyStatus": {"IsPublic": False}
    }
    return client


def _check(client):
    return inspect_locked_bucket_read_only(
        client=client, bucket="dedicated-locked-official-pdfs",
    )


def test_secure_bucket_passes_using_only_read_only_api_calls():
    client = _secure_client()
    result = _check(client)
    assert result.ready
    assert result.issues == ()
    assert not any(
        name.startswith(("put_", "delete_", "create_", "upload_"))
        for name in client.method_calls
    )
    assert len(client.method_calls) == 5


@pytest.mark.parametrize("method,return_value,issue", [
    ("get_bucket_versioning", {"Status": "Suspended"}, "versioning:not_enabled"),
    ("get_object_lock_configuration", {"ObjectLockConfiguration": {
        "ObjectLockEnabled": "Enabled",
        "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Years": 10}},
    }}, "object_lock:compliance_default_missing"),
    ("get_object_lock_configuration", {"ObjectLockConfiguration": {
        "ObjectLockEnabled": "Enabled",
        "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 90}},
    }}, "object_lock:default_retention_too_short"),
    ("get_public_access_block", {"PublicAccessBlockConfiguration": {
        "BlockPublicAcls": True, "IgnorePublicAcls": True,
        "BlockPublicPolicy": False, "RestrictPublicBuckets": True,
    }}, "public_access:not_fully_blocked"),
    ("get_bucket_encryption", {"ServerSideEncryptionConfiguration": {
        "Rules": [],
    }}, "encryption:default_missing"),
    ("get_bucket_policy_status", {"PolicyStatus": {
        "IsPublic": True,
    }}, "bucket_policy:public_or_unknown"),
])
def test_missing_bucket_protection_fails_closed(method, return_value, issue):
    client = _secure_client()
    getattr(client, method).return_value = return_value
    result = _check(client)
    assert not result.ready
    assert issue in result.issues


@pytest.mark.parametrize("method", [
    "get_bucket_versioning", "get_object_lock_configuration",
    "get_public_access_block", "get_bucket_encryption",
    "get_bucket_policy_status",
])
def test_unreadable_bucket_security_configuration_fails_closed(method):
    client = _secure_client()
    getattr(client, method).side_effect = PermissionError("AccessDenied")
    result = _check(client)
    assert not result.ready
    assert f"{method.removeprefix('get_').replace('bucket_', '')}:inspection_failed" not in result.issues or result.issues
    assert "inspection_failed" in " ".join(result.issues)


def test_invalid_bucket_identity_rejected_before_any_provider_access():
    client = _secure_client()
    with pytest.raises(ValueError):
        inspect_locked_bucket_read_only(client=client, bucket="")
    client.assert_not_called()
