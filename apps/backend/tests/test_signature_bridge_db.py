"""Database-backed staging signature inbox regression tests.

An isolated ephemeral SQLite database exercises real ORM writes and indexed
alias lookup. Production parity still requires separate PostgreSQL migration
certification before any deployment.
"""
import base64
import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException, Response
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from database.models.enums import UserRole
from database.models.signature_bridge import SignatureBridgeImport, SignatureBridgePhoneAlias
from routers.signature_bridge import (
    ClientLookupRequest, SignatureImportRequest, import_signature, resolve_client, resolve_officer,
)


@pytest.fixture
def database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SignatureBridgeImport.__table__.create(bind=engine)
    SignatureBridgePhoneAlias.__table__.create(bind=engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("LOANHUB_SIGNATURE_BRIDGE_IMPORT_ENABLED", "true")
    monkeypatch.setenv("LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY", Fernet.generate_key().decode())


def actor(company_id=None, user_id=None):
    return SimpleNamespace(
        company_id=company_id or uuid4(),
        user=SimpleNamespace(id=user_id or uuid4()),
        staff=SimpleNamespace(role=UserRole.COMPANY_ADMIN),
        is_platform_admin=False,
    )


def capture(signer_id, phone, source=None, data=b"synthetic-test-capture"):
    return SignatureImportRequest(
        source_record_id=source or uuid4(),
        signer_kind="client",
        verified_signer_id=signer_id,
        consent_reference="staging-consent-verified-elsewhere",
        phone_numbers=phone,
        capture_base64=base64.b64encode(data).decode(),
        capture_sha256=hashlib.sha256(data).hexdigest(),
    )


def test_import_writes_ciphertext_and_normalized_individual_aliases(database, enabled):
    tenant = actor()
    signer = uuid4()
    request = capture(signer, "58123456 / +26663123456")
    result = import_signature(request, Response(), database, tenant)
    assert result["status"] == "pending_identity_review"
    assert result["usable_for_signing"] is False

    row = database.query(SignatureBridgeImport).one()
    assert row.company_id == tenant.company_id
    assert row.signer_id == signer
    assert row.payload_ciphertext != b"synthetic-test-capture"
    assert Fernet(
        __import__("os").environ["LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY"].encode()
    ).decrypt(row.payload_ciphertext) == b"synthetic-test-capture"
    assert database.query(SignatureBridgePhoneAlias).count() == 2

    result = resolve_client(
        ClientLookupRequest(phones="63123456"), Response(), database, tenant
    )
    assert result["status"] == "pending_identity_review"
    assert result["match_count"] == 1
    assert result["signature_available_for_form"] is False


def test_duplicate_retry_does_not_create_new_rows(database, enabled):
    tenant = actor()
    request = capture(uuid4(), "58123456")
    first = import_signature(request, Response(), database, tenant)
    second = import_signature(request, Response(), database, tenant)
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert database.query(SignatureBridgeImport).count() == 1
    assert database.query(SignatureBridgePhoneAlias).count() == 1


def test_same_source_modified_payload_is_conflict(database, enabled):
    tenant = actor()
    first = capture(uuid4(), "58123456")
    import_signature(first, Response(), database, tenant)
    modified = first.model_copy(update={
        "capture_base64": base64.b64encode(b"different-capture").decode(),
        "capture_sha256": hashlib.sha256(b"different-capture").hexdigest(),
    })
    with pytest.raises(HTTPException) as error:
        import_signature(modified, Response(), database, tenant)
    assert error.value.status_code == 409
    assert database.query(SignatureBridgeImport).count() == 1


def test_two_phone_aliases_different_signatures_report_conflict(database, enabled):
    tenant = actor()
    import_signature(capture(uuid4(), "58123456"), Response(), database, tenant)
    import_signature(capture(uuid4(), "63123456"), Response(), database, tenant)
    result = resolve_client(
        ClientLookupRequest(phones="58123456/63123456"),
        Response(), database, tenant
    )
    assert result["status"] == "conflict"
    assert result["match_count"] == 2
    assert result["signature_available_for_form"] is False


def test_cross_company_records_not_disclosed(database, enabled):
    first = actor()
    second = actor()
    import_signature(capture(uuid4(), "58123456"), Response(), database, first)
    result = resolve_client(
        ClientLookupRequest(phones="58123456"), Response(), database, second
    )
    assert result["status"] == "not_found"
    assert result["match_count"] == 0
