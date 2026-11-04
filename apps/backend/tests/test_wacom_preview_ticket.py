"""Unit tests: Ed25519 preview tickets are signed and strictly scoped."""

import base64
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from services.wacom_preview_ticket import issue_wacom_preview_ticket

NOW = datetime(2026, 11, 4, 11, tzinfo=timezone.utc)
COMPANY, OPERATOR, CONTRACT, SESSION, WORKSTATION = (uuid4() for _ in range(5))
HASH = "a" * 64


def active():
    return SimpleNamespace(
        id=SESSION, company_id=COMPANY, operator_user_id=OPERATOR,
        contract_id=CONTRACT, contract_hash=HASH,
        status="created", evidence_sha256=None,
        expires_at=NOW + timedelta(minutes=3),
    )


def arguments():
    return dict(
        signing_key=Ed25519PrivateKey.generate(), key_id="wacom-preview-key-1",
        session=active(), authenticated_company_id=COMPANY,
        authenticated_operator_id=OPERATOR, current_contract_id=CONTRACT,
        current_contract_hash=HASH, expected_session_id=SESSION,
        authorized_workstation_id=WORKSTATION, now=NOW,
    )


def decode(segment):
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def test_issue_has_verified_signature_bounded_expiry_and_scope():
    kwargs = arguments()
    ticket = issue_wacom_preview_ticket(**kwargs)
    parts = ticket.split(".")
    assert len(parts) == 3
    kwargs["signing_key"].public_key().verify(decode(parts[2]), ".".join(parts[:2]).encode("ascii"))
    header = json.loads(decode(parts[0]))
    claims = json.loads(decode(parts[1]))
    assert header == {"alg": "EdDSA", "kid": "wacom-preview-key-1", "typ": "WACOM-PREVIEW"}
    assert claims["purpose"] == "test-preview-only"
    assert claims["aud"] == "loanhub-wacom-connector-preview-v1"
    assert claims["workstation_id"] == str(WORKSTATION)
    assert claims["contract_hash"] == HASH
    assert claims["company_id"] == str(COMPANY)
    assert claims["session_id"] == str(SESSION)
    assert 0 < claims["exp"] - claims["iat"] <= 60
    with pytest.raises(InvalidSignature):
        kwargs["signing_key"].public_key().verify(decode(parts[2]), (parts[0] + "." + parts[1] + "tampered").encode("ascii"))


def test_different_tickets_have_unique_jti():
    kwargs = arguments()
    a = json.loads(decode(issue_wacom_preview_ticket(**kwargs).split(".")[1]))
    b = json.loads(decode(issue_wacom_preview_ticket(**kwargs).split(".")[1]))
    assert a["jti"] != b["jti"]


@pytest.mark.parametrize("mutation", [
    {"authenticated_company_id": uuid4()},
    {"authenticated_operator_id": uuid4()},
    {"current_contract_id": uuid4()},
    {"current_contract_hash": "b" * 64},
    {"expected_session_id": uuid4()},
])
def test_authorization_failure_does_not_issue_ticket(mutation):
    kwargs = arguments()
    kwargs.update(mutation)
    with pytest.raises(HTTPException):
        issue_wacom_preview_ticket(**kwargs)


def test_rejects_untrusted_key_and_unbounded_duration():
    kwargs = arguments()
    kwargs["signing_key"] = b"not a signing key"
    with pytest.raises(ValueError):
        issue_wacom_preview_ticket(**kwargs)
    kwargs = arguments()
    kwargs["lifetime"] = timedelta(minutes=3)
    with pytest.raises(ValueError):
        issue_wacom_preview_ticket(**kwargs)


def test_ticket_cannot_outlive_persisted_session():
    kwargs = arguments()
    kwargs["session"].expires_at = NOW + timedelta(seconds=7)
    claims = json.loads(decode(issue_wacom_preview_ticket(**kwargs).split(".")[1]))
    assert claims["exp"] - claims["iat"] == 7
