"""Read-only preflight for a dedicated official-document S3 Object Lock bucket.

This inspector does not create, overwrite, delete, retain or fetch PDF objects.
It intentionally fails closed on missing permissions or incomplete S3 security
configuration. A passing result is a prerequisite, not certification: staging
must separately prove a retained version resists overwrite/delete and can be
read by exact VersionId with the intended restricted IAM roles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_REQUIRED_PUBLIC_ACCESS_BLOCKS = (
    "BlockPublicAcls", "IgnorePublicAcls",
    "BlockPublicPolicy", "RestrictPublicBuckets",
)


@dataclass(frozen=True)
class LockedBucketPreflight:
    bucket: str
    ready: bool
    issues: tuple[str, ...]


def inspect_locked_bucket_read_only(*, client: Any, bucket: str) -> LockedBucketPreflight:
    """Inspect actual provider controls without mutating an object or policy.

    Broad exception handling is deliberate: lack of permission to inspect a
    protection must NEVER be treated as evidence that it exists.
    """
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("A dedicated official-document bucket is required")
    issues: list[str] = []

    def inspect(label: str, operation):
        try:
            return operation()
        except Exception:
            issues.append(f"{label}:inspection_failed")
            return None

    versioning = inspect(
        "versioning", lambda: client.get_bucket_versioning(Bucket=bucket),
    )
    if versioning is not None and versioning.get("Status") != "Enabled":
        issues.append("versioning:not_enabled")

    locking = inspect(
        "object_lock", lambda: client.get_object_lock_configuration(Bucket=bucket),
    )
    if locking is not None:
        config = locking.get("ObjectLockConfiguration") or {}
        if config.get("ObjectLockEnabled") != "Enabled":
            issues.append("object_lock:not_enabled")
        default = (config.get("Rule") or {}).get("DefaultRetention") or {}
        # A COMPLIANCE default is an additional defense. Object-level uploads
        # explicitly specify COMPLIANCE, but absent default retention leaves
        # new objects from other upload paths unprotected.
        if default.get("Mode") != "COMPLIANCE":
            issues.append("object_lock:compliance_default_missing")
        if not (isinstance(default.get("Days"), int)
                and default["Days"] >= 3650) and not (
                    isinstance(default.get("Years"), int)
                    and default["Years"] >= 10
                ):
            issues.append("object_lock:default_retention_too_short")

    public_access = inspect(
        "public_access", lambda: client.get_public_access_block(Bucket=bucket),
    )
    if public_access is not None:
        controls = public_access.get("PublicAccessBlockConfiguration") or {}
        if not all(controls.get(name) is True for name in _REQUIRED_PUBLIC_ACCESS_BLOCKS):
            issues.append("public_access:not_fully_blocked")

    encryption = inspect(
        "encryption", lambda: client.get_bucket_encryption(Bucket=bucket),
    )
    if encryption is not None:
        rules = (encryption.get("ServerSideEncryptionConfiguration") or {}).get("Rules") or []
        supported = any(
            (rule.get("ApplyServerSideEncryptionByDefault") or {}).get("SSEAlgorithm")
            in {"AES256", "aws:kms"}
            for rule in rules
        )
        if not supported:
            issues.append("encryption:default_missing")

    policy_status = inspect(
        "bucket_policy", lambda: client.get_bucket_policy_status(Bucket=bucket),
    )
    if policy_status is not None and (
        (policy_status.get("PolicyStatus") or {}).get("IsPublic") is not False
    ):
        issues.append("bucket_policy:public_or_unknown")

    return LockedBucketPreflight(
        bucket=bucket, ready=not issues, issues=tuple(issues),
    )
