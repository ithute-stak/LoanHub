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
    monkeypatch.setattr(api, "reserve_lookup_attempt", lambda db, **scope: None)
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
    assert response["company_id"] == str(context.company_id)
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



def test_concurrent_retry_is_accepted_only_for_same_capture(context, enabled):
    from sqlalchemy.exc import IntegrityError
    from services.signature_bridge_matching import normalized_phone_aliases
    import hmac
    import os
    record = payload()
    key = base64.urlsafe_b64decode(os.environ["LOANHUB_SIGNATURE_BRIDGE_VAULT_KEY"])
    aliases = normalized_phone_aliases(record.phone_numbers)
    alias_hash = hmac.new(key, (str(context.company_id) + "|" + "|".join(aliases)).encode(), hashlib.sha256).hexdigest()
    existing = SimpleNamespace(payload_sha256=record.capture_sha256, signer_id=record.verified_signer_id, signer_kind=record.signer_kind, consent_reference=record.consent_reference, phone_aliases_digest=alias_hash)
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.side_effect = [None, existing]
    db.flush.side_effect = IntegrityError("INSERT", {}, RuntimeError("unique violation"))
    result = api.import_signature(record, Response(), db, context)
    assert result["duplicate"] is True
    assert result["usable_for_signing"] is False
    db.rollback.assert_called_once()


def test_concurrent_conflicting_retry_remains_409(context, enabled):
    from sqlalchemy.exc import IntegrityError
    record = payload()
    existing = SimpleNamespace(payload_sha256="0" * 64, signer_id=record.verified_signer_id, signer_kind=record.signer_kind, consent_reference=record.consent_reference, phone_aliases_digest="0" * 64)
    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.side_effect = [None, existing]
    db.flush.side_effect = IntegrityError("INSERT", {}, RuntimeError("unique violation"))
    with pytest.raises(HTTPException) as error:
        api.import_signature(record, Response(), db, context)
    assert error.value.status_code == 409
    db.rollback.assert_called_once()

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

def test_exact_national_id_lookup_requires_staging_gate(context, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    db = MagicMock()
    with pytest.raises(HTTPException) as err:
        api.lookup_national_id(api.NationalIdLookupRequest(national_id="ABC1234"), Response(), db, context)
    assert err.value.status_code == 503
    db.query.assert_not_called()


def test_national_id_lookup_reports_full_name_and_saved_signature(context, enabled):
    borrower_id = uuid4()
    db = MagicMock()
    queries = [MagicMock(), MagicMock(), MagicMock()]
    db.query.side_effect = queries
    queries[0].join.return_value.join.return_value.filter.return_value.limit.return_value.all.return_value = [
        (borrower_id, "Thabo", "M.", "Mokoena")
    ]
    queries[1].filter.return_value.limit.return_value.all.return_value = [(uuid4(),)]
    queries[2].filter.return_value.limit.return_value.all.return_value = []
    data = api.lookup_national_id(api.NationalIdLookupRequest(national_id="ABC1234"), Response(), db, context)
    assert data["status"] == "existing_signature"
    assert data["matches"][0]["full_name"] == "Thabo M. Mokoena"
    assert data["matches"][0]["borrower_id"] == str(borrower_id)
    assert data["matches"][0]["signature_state"] == "active_saved"
    assert data["may_capture"] is False
    assert data["may_reuse"] is False
    assert data["may_sign_contract"] is False


def test_national_id_lookup_pending_import_blocks_recapture(context, enabled):
    db = MagicMock()
    queries = [MagicMock(), MagicMock(), MagicMock()]
    db.query.side_effect = queries
    queries[0].join.return_value.join.return_value.filter.return_value.limit.return_value.all.return_value = [
        (uuid4(), "Lineo", None, "Molefe")
    ]
    queries[1].filter.return_value.limit.return_value.all.return_value = []
    queries[2].filter.return_value.limit.return_value.all.return_value = [(uuid4(),)]
    data = api.lookup_national_id(api.NationalIdLookupRequest(national_id="ABCD098"), Response(), db, context)
    assert data["status"] == "pending_signature_review"
    assert data["matches"][0]["full_name"] == "Lineo Molefe"
    assert data["may_capture"] is False


def test_national_id_lookup_does_not_disclose_unknown_records(context, enabled):
    db = MagicMock()
    db.query.return_value.join.return_value.join.return_value.filter.return_value.limit.return_value.all.return_value = []
    data = api.lookup_national_id(api.NationalIdLookupRequest(national_id="ABCD123"), Response(), db, context)
    assert data["status"] == "not_found"
    assert data["matches"] == []
    assert data["may_capture"] is False



def test_national_id_lookup_filters_company_and_borrower_in_all_queries(context, enabled):
    """Ensure every identity/signature query is scoped to one verified tenant."""
    borrower = uuid4()
    db = MagicMock()
    queries = [MagicMock(), MagicMock(), MagicMock()]
    db.query.side_effect = queries
    queries[0].join.return_value.join.return_value.filter.return_value.limit.return_value.all.return_value = [
        (borrower, "Mpho", None, "Motaung")
    ]
    queries[1].filter.return_value.limit.return_value.all.return_value = []
    queries[2].filter.return_value.limit.return_value.all.return_value = []
    answer = api.lookup_national_id(
        api.NationalIdLookupRequest(national_id="ABCD5678"), Response(), db, context
    )
    assert answer["status"] == "matched_no_signature"
    assert answer["matches"][0]["full_name"] == "Mpho Motaung"
    assert answer["may_capture"] is False
    # Render the actual SQLAlchemy predicates; mocking returned results alone
    # cannot detect a regression that drops tenant or borrower constraints.
    first_predicates = queries[0].join.return_value.join.return_value.filter.call_args.args
    saved_predicates = queries[1].filter.call_args.args
    pending_predicates = queries[2].filter.call_args.args
    compiled = lambda expressions: " AND ".join(
        str(expression.compile(compile_kwargs={"literal_binds": True}))
        for expression in expressions
    )
    first_sql = compiled(first_predicates)
    saved_sql = compiled(saved_predicates)
    pending_sql = compiled(pending_predicates)
    for statement in (first_sql, saved_sql, pending_sql):
        assert str(context.company_id) in statement
        assert "company_id" in statement
    for statement in (saved_sql, pending_sql):
        assert str(borrower) in statement
        assert "borrower_id" in statement or "signer_id" in statement
    assert "people.national_id" in first_sql
    assert "ABCD5678" in first_sql


def test_national_id_lookup_audit_attempt_precedes_client_database_query(context, enabled, monkeypatch):
    """No identity record may be returned before the audit budget is reserved."""
    db = MagicMock()
    def refuse(*_args, **_kwargs):
        raise HTTPException(429, "Lookup budget exhausted")
    monkeypatch.setattr(api, "reserve_lookup_attempt", refuse)
    with pytest.raises(HTTPException) as raised:
        api.lookup_national_id(
            api.NationalIdLookupRequest(national_id="ABCD5678"), Response(), db, context
        )
    assert raised.value.status_code == 429
    db.query.assert_not_called()


def test_pending_signature_review_does_not_grant_reuse(context, enabled):
    db = MagicMock()
    queries = [MagicMock(), MagicMock(), MagicMock()]
    db.query.side_effect = queries
    queries[0].join.return_value.join.return_value.filter.return_value.limit.return_value.all.return_value = [
        (uuid4(), "Mpho", None, "Motaung")
    ]
    queries[1].filter.return_value.limit.return_value.all.return_value = []
    queries[2].filter.return_value.limit.return_value.all.return_value = [(uuid4(),)]
    result = api.lookup_national_id(
        api.NationalIdLookupRequest(national_id="ABCD5678"), Response(), db, context
    )
    assert result["status"] == "pending_signature_review"
    assert result["may_capture"] is False
    assert result["may_reuse"] is False
    assert result["may_sign_contract"] is False
