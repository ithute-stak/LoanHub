"""Experimental version-pinned S3 Object Lock adapter for official LoanHub PDFs.

This does not replace existing ManagedFile storage or enable issuance. The
issuance schema must persist immutable object keys AND version IDs, and the
read path must use version_id before this adapter can be wired in.

Requires an Object Lock-enabled, versioned S3 bucket with a reviewed retention
policy. An ordinary S3 overwrite or ETag is NOT evidence of immutability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from services.object_storage_service import StorageUnavailableError, _safe_key


@dataclass(frozen=True)
class LockedPdfObject:
    bucket: str
    key: str
    version_id: str
    sha256_hex: str
    retain_until: datetime


class S3ObjectLockPdfStore:
    """S3 COMPLIANCE retention with explicit immutable version reads."""

    provider = "s3_object_lock"

    def __init__(
        self, *, client: Any, bucket: str, prefix: str = "official-issuances",
        retention_days: int = 3650,
    ) -> None:
        if not isinstance(bucket, str) or not bucket.strip():
            raise ValueError("A dedicated immutable PDF bucket is required")
        if type(retention_days) is not int or retention_days < 1:
            raise ValueError("Positive retention period is required")
        self.client = client
        self.bucket = bucket
        self.prefix = _safe_key(prefix)
        self.retention_days = retention_days

    def _key(self, tenant_id: str, public_id: str) -> str:
        if not isinstance(tenant_id, str) or not tenant_id:
            raise ValueError("Tenant identity required")
        if not isinstance(public_id, str) or not (12 <= len(public_id) <= 96):
            raise ValueError("Valid public identity required")
        if not all(c.isascii() and (c.isalnum() or c in "-_") for c in public_id):
            raise ValueError("Invalid public ID")
        return f"{self.prefix}/{_safe_key(tenant_id)}/{public_id}.pdf"

    def assert_bucket_ready(self) -> None:
        try:
            versioning = self.client.get_bucket_versioning(Bucket=self.bucket)
            locking = self.client.get_object_lock_configuration(Bucket=self.bucket)
        except Exception as exc:
            raise StorageUnavailableError("Cannot verify immutable bucket capabilities") from exc
        if versioning.get("Status") != "Enabled" or (
            locking.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") != "Enabled"
        ):
            raise StorageUnavailableError("Bucket must have Object Lock and versioning enabled")

    def put_locked_pdf(
        self, *, tenant_id: str, public_id: str, pdf: bytes,
    ) -> LockedPdfObject:
        if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-"):
            raise ValueError("Official PDF bytes required")
        self.assert_bucket_ready()
        key = self._key(tenant_id, public_id)
        expiry = datetime.now(timezone.utc) + timedelta(days=self.retention_days)
        try:
            result = self.client.put_object(
                Bucket=self.bucket, Key=key, Body=pdf,
                ContentType="application/pdf", ServerSideEncryption="AES256",
                ObjectLockMode="COMPLIANCE", ObjectLockRetainUntilDate=expiry,
                Metadata={"sha256": sha256(pdf).hexdigest()},
            )
            version_id = result.get("VersionId")
            if not isinstance(version_id, str) or not version_id or version_id == "null":
                raise StorageUnavailableError("S3 returned no immutable object version ID")
            retention = self.client.get_object_retention(
                Bucket=self.bucket, Key=key, VersionId=version_id,
            ).get("Retention", {})
        except StorageUnavailableError:
            raise
        except Exception as exc:
            raise StorageUnavailableError("Immutable PDF upload or retention proof failed") from exc
        locked_until = retention.get("RetainUntilDate")
        if (retention.get("Mode") != "COMPLIANCE"
                or not isinstance(locked_until, datetime)
                or locked_until.tzinfo is None
                or locked_until.astimezone(timezone.utc) < expiry):
            raise StorageUnavailableError("Uploaded PDF retention could not be verified")
        return LockedPdfObject(
            bucket=self.bucket, key=key, version_id=version_id,
            sha256_hex=sha256(pdf).hexdigest(),
            retain_until=locked_until,
        )

    def assert_version_retention(self, record: LockedPdfObject) -> None:
        """Re-check provider retention on the *exact* stored version.

        The SQL retention timestamp is a historical claim, not a substitute
        for the provider's current Object Lock state. A version that can no
        longer prove COMPLIANCE retention is not certified as immutable.
        """
        if (record.bucket != self.bucket or not record.key
                or not isinstance(record.version_id, str)
                or not record.version_id or record.version_id == "null"):
            raise ValueError("Invalid immutable artifact reference")
        if (not isinstance(record.retain_until, datetime)
                or record.retain_until.tzinfo is None):
            raise StorageUnavailableError("Persisted retention deadline is invalid")
        try:
            retention = self.client.get_object_retention(
                Bucket=self.bucket, Key=record.key, VersionId=record.version_id,
            ).get("Retention") or {}
        except Exception as exc:
            raise StorageUnavailableError("Cannot inspect exact PDF version retention") from exc
        provider_until = retention.get("RetainUntilDate")
        if (retention.get("Mode") != "COMPLIANCE"
                or not isinstance(provider_until, datetime)
                or provider_until.tzinfo is None
                or provider_until.astimezone(timezone.utc) < record.retain_until.astimezone(timezone.utc)
                or provider_until.astimezone(timezone.utc) <= datetime.now(timezone.utc)):
            raise StorageUnavailableError("Exact PDF version lacks valid COMPLIANCE retention")

    def read_exact_version(self, record: LockedPdfObject) -> bytes:
        if record.bucket != self.bucket or not record.version_id:
            raise ValueError("Immutable artifact does not match configured bucket")
        try:
            response = self.client.get_object(
                Bucket=self.bucket, Key=record.key, VersionId=record.version_id,
            )
            data = response["Body"].read()
        except Exception as exc:
            raise StorageUnavailableError("Immutable PDF version unavailable") from exc
        if sha256(data).hexdigest() != record.sha256_hex:
            raise StorageUnavailableError("Immutable PDF version fingerprint mismatch")
        return data
