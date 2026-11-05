"""Isolated route-level guards for the staging signature inbox.

These tests do not authorize reuse of customer signatures; all results remain
quarantined until a signer-verified, document-specific workflow exists.
"""
import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException, Response

from database.models.enums import UserRole
from routers import signature_bridge as api


@pytest.fixture
def context():
    return SimpleNamespace(
        company_id=uuid4(),
        user=SimpleNamespace(id=uuid4()),
        staff=SimpleNamespace(role=UserRole.COMPANY_ADMIN),
        is_platform_admin=False,
    )


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("LOANHUB_SIGNATURE_BRIDGE_IMPORT_ENABLED", "true")
    monkeypatch.setenv("LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY", Fernet.generate_key().decode())


def payload(*, signer_kind="client", signer_id=None, phones="58123456 / 63123456"):
    raw = b"synthetic-signature-capture-not-customer-data"
    return api.SignatureImportRequest(
        source_record_id=uuid4(), signer_kind=signer_kind,
        verified_signer_id=signer_id or uuid4(),
        consent_reference="staging-test-only",
        phone_numbers=phones if signer_kind == "client" else None,
        capture_base64=base64.b64encode(raw).decode(),
        capture_sha256=hashlib.sha256(raw).hexdigest(),
    )


def test_client_invalid_phone_returns_422_before_db_write(context, enabled):
    db = MagicMock()
    record = payload(phones="58123456 /")
    with pytest.raises(HTTPException) as error:
        api.import_signature(record, Response(), db, context)
    assert error.value.status_code == 422
    db.add.assert_not_called()


def test_officer_cannot_import_another_users_signature(context, enabled):
    db = MagicMock()
    record = payload(signer_kind="officer", signer_id=uuid4())
    with pytest.raises(HTTPException) as error:
        api.import_signature(record, Response(), db, context)
    assert error.value.status_code == 403
    db.add.assert_not_called()


def test_duplicate_import_is_idempotent_but_never_signs(context, enabled):
    db = MagicMock()
    record = payload()
    existing = SimpleNamespace(
        payload_sha256=record.capture_sha256,
        signer_id=record.verified_signer_id,
        signer_kind=record.signer_kind,
        consent_reference=record.consent_reference,
        phone_aliases_digest=None,
    )
    db.query.return_value.filter.return_value.one_or_none.return_value = existing
    # Set the digest from the same company-bound procedure as the actual route.
    import os
    import hmac
    from services.signature_bridge_matching import normalized_phone_aliases
    digests = normalized_phone_aliases(record.phone_numbers)
    key = base64.urlsafe_b64decode(os.environ["LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY"])
    existing.phone_aliases_digest = hmac.new(
        key, (str(context.company_id) + "|" + "|".join(digests)).encode(),
        hashlib.sha256,
    ).hexdigest()
    response = api.import_signature(record, Response(), db, context)
    assert response["duplicate"] is True
    assert response["usable_for_signing"] is False
    db.add.assert_not_called()


def test_duplicate_record_with_different_payload_returns_409(context, enabled):
    db = MagicMock()
    record = payload()
    db.query.return_value.filter.return_value.one_or_none.return_value = SimpleNamespace(
        payload_sha256="0" * 64,
        signer_id=record.verified_signer_id,
        signer_kind=record.signer_kind,
        consent_reference=record.consent_reference,
        phone_aliases_digest="0" * 64,
    )
    with pytest.raises(HTTPException) as error:
        api.import_signature(record, Response(), db, context)
    assert error.value.status_code == 409


def test_client_lookup_detects_two_signature_records(context, enabled):
    db = MagicMock()
    db.query.return_value.join.return_value.filter.return_value.distinct.return_value.all.return_value = [
        (uuid4(), uuid4()), (uuid4(), uuid4())
    ]
    result = api.resolve_client(api.ClientLookupRequest(phones="58123456 / 63123456"), Response(), db, context)
    assert result["status"] == "conflict"
    assert result["match_count"] == 2
    assert result["signature_available_for_form"] is False


def test_officer_lookup_uses_authenticated_identity(context, enabled):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [(uuid4(),)]
    result = api.resolve_officer(Response(), db, context)
    assert result["status"] == "pending_identity_review"
    assert result["auto_apply"] is False
    assert result["signature_available_for_form"] is False
