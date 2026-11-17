"""Storage must remain disabled until verified, version-pinned immutability."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.document_issuance_storage_readiness import (
    ImmutableDocumentStorageUnavailable,
    require_immutable_document_storage_ready,
)


@pytest.mark.parametrize("provider", ["local", "s3", "minio", "unknown"])
def test_no_ordinary_storage_provider_may_claim_immutable_issuance(provider):
    with patch("services.document_issuance_storage_readiness.get_storage",
               return_value=SimpleNamespace(provider=provider)):
        with pytest.raises(ImmutableDocumentStorageUnavailable):
            require_immutable_document_storage_ready(db=object())


def test_storage_failure_does_not_silently_approve_issuance():
    with patch("services.document_issuance_storage_readiness.get_storage",
               side_effect=RuntimeError("storage unavailable")):
        with pytest.raises(RuntimeError, match="storage unavailable"):
            require_immutable_document_storage_ready(db=object())
