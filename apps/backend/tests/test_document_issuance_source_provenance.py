"""Source authorization is anchored in the actual private ManagedFile row."""
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from services.document_issuance_source_provenance import (
    load_authorized_managed_pdf_source, stage_authorized_managed_pdf_source,
)


PDF = b"%PDF-1.4\nowned source\n"


def _fixture():
    tenant, user, file_id = uuid4(), uuid4(), uuid4()
    context = SimpleNamespace(
        company_id=tenant, company=SimpleNamespace(id=tenant),
        user=SimpleNamespace(id=user),
        staff=SimpleNamespace(role=UserRole.COMPANY_ADMIN),
        is_platform_admin=False,
    )
    source = SimpleNamespace(
        id=file_id, company_id=tenant, owner_user_id=user,
        is_deleted=False, is_confidential=True,
        visibility="private", scan_status="clean",
        mime_type="application/pdf", checksum_sha256=sha256(PDF).hexdigest(),
    )
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = source
    return db, context, file_id, source


def _load(db, context, file_id):
    return load_authorized_managed_pdf_source(
        db=db, context=context, source_file_id=file_id,
    )


def test_exact_private_clean_owned_pdf_can_be_resolved():
    db, context, file_id, _ = _fixture()
    with patch("services.document_issuance_source_provenance.read_file_bytes",
               return_value=PDF) as reader:
        result = _load(db, context, file_id)
    assert result.pdf_bytes == PDF
    assert result.source_file_id == file_id
    assert result.tenant_id == context.company_id
    assert result.sha256_hex == sha256(PDF).hexdigest()
    reader.assert_called_once()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("change", [
    {"company_id": uuid4()}, {"owner_user_id": uuid4()},
    {"is_deleted": True}, {"is_confidential": False},
    {"visibility": "public"}, {"scan_status": "validated"},
    {"mime_type": "image/png"}, {"id": uuid4()},
])
def test_invalid_file_identity_or_security_does_not_read_bytes(change):
    db, context, file_id, source = _fixture()
    for key, value in change.items():
        setattr(source, key, value)
    with patch("services.document_issuance_source_provenance.read_file_bytes") as reader:
        with pytest.raises(PermissionError, match="tenant-owned source"):
            _load(db, context, file_id)
    reader.assert_not_called()


def test_missing_file_fails_closed():
    db, context, file_id, _ = _fixture()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(PermissionError):
        _load(db, context, file_id)


def test_wrong_stored_hash_rejected():
    db, context, file_id, source = _fixture()
    source.checksum_sha256 = "0" * 64
    with patch("services.document_issuance_source_provenance.read_file_bytes", return_value=PDF):
        with pytest.raises(ValueError, match="fingerprint mismatch"):
            _load(db, context, file_id)


def test_borrower_cannot_load_official_tenant_source():
    db, context, file_id, _ = _fixture()
    context.staff.role = UserRole.LOAN_OFFICER
    with pytest.raises(HTTPException) as denied:
        _load(db, context, file_id)
    assert denied.value.status_code == 403
    db.query.assert_not_called()


def test_unverified_tenant_context_rejected_before_query():
    db, context, file_id, _ = _fixture()
    context.company.id = uuid4()
    with pytest.raises(PermissionError):
        _load(db, context, file_id)
    db.query.assert_not_called()


def test_staging_entry_point_uses_only_verified_managed_file_bytes():
    db, context, file_id, source = _fixture()
    store = object()
    with patch("services.document_issuance_source_provenance.read_file_bytes",
               return_value=PDF), patch(
        "services.document_issuance_immutable_staging.stage_locked_document_candidate",
        return_value="staged-result",
    ) as stage:
        result = stage_authorized_managed_pdf_source(
            db=db, context=context, source_file_id=file_id,
            trusted_verification_origin="https://verify.example.test",
            store=store, stamp_configuration_version=2,
        )
    assert result == "staged-result"
    stage.assert_called_once_with(
        context=context, source_pdf=PDF,
        trusted_verification_origin="https://verify.example.test",
        store=store, db=db, stamp_configuration_version=2,
    )


def test_staging_entry_point_denies_cross_tenant_source_before_staging():
    db, context, file_id, source = _fixture()
    source.company_id = uuid4()
    with patch("services.document_issuance_immutable_staging.stage_locked_document_candidate") as stage:
        with pytest.raises(PermissionError):
            stage_authorized_managed_pdf_source(
                db=db, context=context, source_file_id=file_id,
                trusted_verification_origin="https://verify.example.test",
                store=object(), stamp_configuration_version=2,
            )
    stage.assert_not_called()
