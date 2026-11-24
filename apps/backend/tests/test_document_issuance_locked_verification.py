"""Locked PDF verification requires exact S3 version and a trusted tenant."""
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from services.document_issuance_immutable_s3 import S3ObjectLockPdfStore
from services.document_issuance_locked_verification import verify_immutable_issuance
from services.object_storage_service import StorageUnavailableError


PDF = b"%PDF-1.4\nlocked verified bytes\n"
PUBLIC_ID = "locked-document-reference-12345"


def _setup():
    tenant = uuid4()
    record = SimpleNamespace(
        company_id=tenant, public_id=PUBLIC_ID,
        status="issued", final_pdf_sha256=sha256(PDF).hexdigest(),
        immutable_bucket="official-documents",
        immutable_object_key="official/tenant/doc.pdf",
        immutable_version_id="version-1",
    )
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = record
    store = object.__new__(S3ObjectLockPdfStore)
    return tenant, db, store, record


def _verify(tenant, db, store, submitted_pdf=None):
    return verify_immutable_issuance(
        db=db, authenticated_tenant_id=tenant, public_id=PUBLIC_ID,
        store=store, submitted_pdf=submitted_pdf,
    )


@pytest.fixture(autouse=True)
def _role_gate():
    with patch("services.document_issuance_locked_verification.require_document_issuance_database_ready"):
        yield


def test_exact_uploaded_pdf_is_verified_after_canonical_version_read():
    tenant, db, store, _ = _setup()
    with patch("services.document_issuance_locked_verification.verify_locked_pdf_for_issuance",
               return_value=PDF) as read:
        assert _verify(tenant, db, store, PDF) == "verified"
    read.assert_called_once()


def test_qr_only_never_returns_verified():
    tenant, db, store, _ = _setup()
    with patch("services.document_issuance_locked_verification.verify_locked_pdf_for_issuance",
               return_value=PDF):
        assert _verify(tenant, db, store) == "issued_file_available_not_compared"


def test_different_submitted_bytes_are_altered():
    tenant, db, store, _ = _setup()
    with patch("services.document_issuance_locked_verification.verify_locked_pdf_for_issuance",
               return_value=PDF):
        assert _verify(tenant, db, store, PDF + b"modified") == "altered"


def test_missing_issuance_record_not_found_without_object_access():
    tenant, db, store, _ = _setup()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with patch("services.document_issuance_locked_verification.verify_locked_pdf_for_issuance") as read:
        assert _verify(tenant, db, store) == "not_found"
    read.assert_not_called()


@pytest.mark.parametrize("status", ["revoked", "superseded"])
def test_inactive_issuances_are_not_verified(status):
    tenant, db, store, record = _setup()
    record.status = status
    with patch("services.document_issuance_locked_verification.verify_locked_pdf_for_issuance") as read:
        assert _verify(tenant, db, store, PDF) == status
    read.assert_not_called()


def test_cross_tenant_record_is_not_disclosed():
    tenant, db, store, record = _setup()
    record.company_id = uuid4()
    with patch("services.document_issuance_locked_verification.verify_locked_pdf_for_issuance") as read:
        assert _verify(tenant, db, store, PDF) == "not_found"
    read.assert_not_called()


def test_missing_locked_version_never_falls_back_to_mutable_storage():
    tenant, db, store, _ = _setup()
    with patch("services.document_issuance_locked_verification.verify_locked_pdf_for_issuance",
               side_effect=StorageUnavailableError("version unavailable")):
        assert _verify(tenant, db, store, PDF) == "unavailable"


def test_unsafe_database_role_denies_lookup():
    tenant, db, store, _ = _setup()
    with patch("services.document_issuance_locked_verification.require_document_issuance_database_ready",
               side_effect=PermissionError("RLS not ready")):
        with pytest.raises(PermissionError, match="RLS not ready"):
            _verify(tenant, db, store)
    db.query.assert_not_called()


def test_wrong_store_adapter_denied_before_database_access():
    tenant, db, _, _ = _setup()
    with pytest.raises(PermissionError, match="Object Lock"):
        _verify(tenant, db, SimpleNamespace(provider="s3"))
    db.query.assert_not_called()
