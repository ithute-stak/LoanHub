from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import services.contract_email_otp_service as otp_service
from services.contract_email_otp_service import _otp_digest, mask_email


def test_mask_email_preserves_domain_without_exposing_local_part():
    assert mask_email("borrower@example.com") == "b*******@example.com"
    assert mask_email("a@example.com") == "a***@example.com"


def test_otp_digest_is_deterministic_and_bound_to_challenge():
    contract_id = "11111111-2222-3333-4444-555555555555"
    first = _otp_digest(contract_id, "ESIGN-ABC", "123456")
    same = _otp_digest(contract_id, "ESIGN-ABC", "123456")
    different_code = _otp_digest(contract_id, "ESIGN-ABC", "654321")
    different_reference = _otp_digest(contract_id, "ESIGN-XYZ", "123456")

    assert first == same
    assert first != different_code
    assert first != different_reference
    assert "123456" not in first


def test_recipient_resolution_prefers_borrower_profile(monkeypatch):
    monkeypatch.setattr(
        otp_service,
        "_borrower_contact",
        lambda _db, _contract: ("Test Borrower", "profile@example.com"),
    )

    name, recipient, source = otp_service._recipient_for_request(
        object(),
        object(),
        "other@example.com",
    )

    assert name == "Test Borrower"
    assert recipient == "profile@example.com"
    assert source == "borrower_profile"


def test_recipient_resolution_accepts_operator_email_only_when_profile_missing(monkeypatch):
    monkeypatch.setattr(
        otp_service,
        "_borrower_contact",
        lambda _db, _contract: ("Test Borrower", None),
    )

    name, recipient, source = otp_service._recipient_for_request(
        object(),
        object(),
        "  CLIENT@Example.COM ",
    )

    assert name == "Test Borrower"
    assert recipient == "client@example.com"
    assert source == "operator_supplied"


def test_recipient_resolution_rejects_missing_or_invalid_fallback(monkeypatch):
    monkeypatch.setattr(
        otp_service,
        "_borrower_contact",
        lambda _db, _contract: ("Test Borrower", None),
    )

    with pytest.raises(HTTPException) as exc_info:
        otp_service._recipient_for_request(object(), object(), "not-an-email")

    assert exc_info.value.status_code == 409
    assert "Enter the borrower email address" in str(exc_info.value.detail)


def test_signing_status_requests_email_when_client_has_none(monkeypatch):
    contract = SimpleNamespace(id="contract-1", company_id="company-1")
    monkeypatch.setattr(
        otp_service,
        "_borrower_contact",
        lambda _db, _contract: ("Test Borrower", None),
    )
    monkeypatch.setattr(otp_service, "_pending_session", lambda _db, _contract: None)
    monkeypatch.setattr(otp_service, "email_transport_ready", lambda _db, _company_id: True)

    status = otp_service.signing_status(object(), contract)

    assert status["borrower_name"] == "Test Borrower"
    assert status["masked_email"] == ""
    assert status["recipient_email_required"] is True
    assert status["email_transport_ready"] is True
    assert status["pending"] is False


def test_signing_status_keeps_masked_operator_email_for_pending_challenge(monkeypatch):
    contract = SimpleNamespace(id="contract-1", company_id="company-1")
    pending = SimpleNamespace(
        due_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5),
        data={"masked_email": "c*****@example.com", "attempts": 1},
    )
    monkeypatch.setattr(
        otp_service,
        "_borrower_contact",
        lambda _db, _contract: ("Test Borrower", None),
    )
    monkeypatch.setattr(otp_service, "_pending_session", lambda _db, _contract: pending)
    monkeypatch.setattr(otp_service, "email_transport_ready", lambda _db, _company_id: True)

    status = otp_service.signing_status(object(), contract)

    assert status["masked_email"] == "c*****@example.com"
    assert status["recipient_email_required"] is False
    assert status["pending"] is True
    assert status["attempts_remaining"] == otp_service.MAX_ATTEMPTS - 1
