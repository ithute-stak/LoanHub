"""Fail-closed storage durability gate for official LoanHub documents.

ManagedFile + ordinary local/S3 put/get is not immutable document retention.
LocalObjectStorage.put() replaces paths, and S3ObjectStorage.put() has no
object-version binding, retention proof or deny-delete enforcement. A hash
detects change but cannot guarantee long-term availability or authenticity.

Do not weaken this guard with an environment-only 'approved' flag. Introduce
an immutable artifact adapter that persists version IDs, provider retention
evidence and read-by-version, plus a recovery policy, before enabling issuance.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from database.models.file_management import ManagedFile
from services.object_storage_service import get_storage


class ImmutableDocumentStorageUnavailable(PermissionError):
    """Official issuance must not proceed on ordinary mutable file storage."""


def require_immutable_document_storage_ready(*, db: Session) -> None:
    """Fail closed until a verifiably immutable, version-pinned adapter exists.

    The explicit storage check is deliberately invoked *before* any PDF is
    generated or stored. This cannot currently succeed on the existing
    providers. The unused db argument reserves the trusted transaction used
    later to bind object-version evidence to an issuance record.
    """
    _ = db
    storage = get_storage()
    provider = getattr(storage, "provider", "")
    if provider in {"local", "s3"}:
        raise ImmutableDocumentStorageUnavailable(
            "Official PDF issuance requires immutable, version-pinned storage; "
            f"the current {provider} adapter does not provide it"
        )
    # Unknown/ad-hoc provider is not evidence of immutability either.
    raise ImmutableDocumentStorageUnavailable(
        "Official PDF issuance requires certified immutable object retention "
        "and verified version-specific reads"
    )
