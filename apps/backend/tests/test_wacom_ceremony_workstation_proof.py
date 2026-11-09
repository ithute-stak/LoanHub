"""Wacom ceremony proof: genuine Ed25519 signing, replay denial, cross-tenant isolation."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace as R
from uuid import uuid4
import base64
import inspect

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException

from services.wacom_ceremony_workstation_proof import (
    PREFIX, ceremony_proof_message, verify_ceremony_workstation_proof,
)
from routers import wacom_ceremony_proofs as routes


def context():
    now = datetime.now(timezone.utc)
    secret = base64.urlsafe_b64encode(b"synthetic-nonce-" * 3).decode("ascii").rstrip("=")
    assert len(secret) == 64
    key = Ed25519PrivateKey.generate()
    company, pc, operator = uuid4(), uuid4(), uuid4()
    row = R(
        id=uuid4(), company_id=company, borrower_id=uuid4(),
        contract_id=uuid4(), intent_id=uuid4(), authorization_id=uuid4(),
        receipt_id=uuid4(), workstation_id=pc,
        candidate_sha256="a"*64, field_binding_sha256="b"*64,
        challenge_sha256=sha256(secret.encode("ascii")).hexdigest(),
        requested_at=now-timedelta(seconds=10),
        expires_at=now+timedelta(seconds=40),
        status="pending", verified_at=None, consumed_at=None,
    )
    enrollment = R(
        company_id=company, workstation_id=pc, status="active",
        revoked_at=None, approved_at=now-timedelta(days=1),
        ed25519_public_key=key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )
    msg = ceremony_proof_message(challenge=row, challenge_secret=secret, operator_id=operator)
    return row, secret, operator, enrollment, key.sign(msg), now


def verify(values):
    row, secret, operator, enrollment, signature, now = values
    return verify_ceremony_workstation_proof(
        challenge=row, challenge_secret=secret, operator_id=operator,
        enrollment=enrollment, signature=signature, now=now,
    )


def test_valid_workstation_key_proof_does_not_sign():
    values=context()
    assert len(verify(values)) == 32
    assert values[0].status == "pending"


def test_wrong_signature_rejected():
    values=list(context())
    values[4]=bytes(64)
    with pytest.raises(HTTPException) as exc:
        verify(values)
    assert exc.value.status_code == 403


def test_other_operator_cannot_replay_signature():
    values=list(context())
    values[2]=uuid4()
    with pytest.raises(HTTPException) as exc:
        verify(values)
    assert exc.value.status_code == 403


def test_other_document_cannot_replay_signature():
    values=list(context())
    values[0].candidate_sha256="f"*64
    with pytest.raises(HTTPException) as exc:
        verify(values)
    assert exc.value.status_code == 403


def test_wrong_secret_cannot_be_substituted():
    values=list(context())
    values[1]="A"*64
    with pytest.raises(HTTPException) as exc:
        verify(values)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("field,value", [
    ("status","verified"),
    ("consumed_at",datetime.now(timezone.utc)),
    ("verified_at",datetime.now(timezone.utc)),
    ("expires_at",datetime.now(timezone.utc)-timedelta(seconds=1)),
])
def test_reused_or_expired_challenge_rejected(field,value):
    values=list(context())
    setattr(values[0],field,value)
    with pytest.raises(HTTPException) as exc:
        verify(values)
    assert exc.value.status_code == 409


def test_revoked_and_cross_company_enrollment_rejected():
    for field,value in (("status","revoked"),("company_id",uuid4())):
        values=list(context())
        setattr(values[3],field,value)
        with pytest.raises(HTTPException) as exc:
            verify(values)
        assert exc.value.status_code == 403


def test_feature_flag_disabled_by_default(monkeypatch):
    monkeypatch.delenv(routes.FEATURE_FLAG,raising=False)
    with pytest.raises(HTTPException) as exc:
        routes._gate()
    assert exc.value.status_code == 503


def test_route_has_exact_session_binding_and_no_contract_execution():
    source=inspect.getsource(routes)
    assert "workstation_id=body.workstation_id" in source
    assert ".with_for_update()" in source
    assert "row.workstation_proof_at = now" in source
    assert '"physical_stu540_pen_verified": False' in source
    assert '"contract_signed": False' in source
    assert "contract.borrower_signed_at =" not in source
    assert "authorization.consumed_at =" not in source


def test_message_domain_separated_from_bridge_proof():
    from services.wacom_bridge_device_proof import PREFIX as bridge
    assert PREFIX != bridge
    assert "CEREMONY" in PREFIX
