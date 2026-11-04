from datetime import datetime, timedelta, timezone
from uuid import uuid4
import base64
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException

from services.wacom_workstation_proof import (
    WacomWorkstationChallenge, challenge_message,
    verify_enrolled_wacom_workstation_proof,
)

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
WORKSTATION, SESSION = uuid4(), uuid4()


def fixture():
    challenge = WacomWorkstationChallenge(
        id=uuid4(), workstation_id=WORKSTATION, session_id=SESSION,
        nonce=base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("="),
        issued_at=NOW, expires_at=NOW + timedelta(seconds=20),
    )
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signature = private.sign(challenge_message(challenge))
    used = set()
    def consume(challenge_id):
        if challenge_id in used:
            return False
        used.add(challenge_id)
        return True
    kwargs = dict(
        challenge=challenge, expected_workstation_id=WORKSTATION,
        expected_session_id=SESSION, enrolled_public_key=public,
        signature=signature, now=NOW + timedelta(seconds=1),
        consume_challenge_once=consume,
    )
    return kwargs


def test_valid_proof_consumed_once():
    kwargs = fixture()
    verify_enrolled_wacom_workstation_proof(**kwargs)
    with pytest.raises(HTTPException) as err:
        verify_enrolled_wacom_workstation_proof(**kwargs)
    assert err.value.status_code == 409


@pytest.mark.parametrize("change", [
    {"expected_workstation_id": uuid4()},
    {"expected_session_id": uuid4()},
    {"now": NOW + timedelta(seconds=20)},
    {"signature": b"0" * 64},
    {"enrolled_public_key": b"0" * 32},
    {"signature": b"invalid"},
])
def test_rejects_wrong_identity_expiry_or_signature(change):
    kwargs = fixture()
    kwargs.update(change)
    with pytest.raises(HTTPException):
        verify_enrolled_wacom_workstation_proof(**kwargs)


def test_replay_outage_fails_closed():
    kwargs = fixture()
    def outage(_):
        raise OSError("database offline")
    kwargs["consume_challenge_once"] = outage
    with pytest.raises(HTTPException) as error:
        verify_enrolled_wacom_workstation_proof(**kwargs)
    assert error.value.status_code == 503


def test_invalid_nonce_or_lifetime_rejected():
    from dataclasses import replace
    kwargs = fixture()
    kwargs["challenge"] = replace(kwargs["challenge"], nonce="bad")
    with pytest.raises(HTTPException):
        verify_enrolled_wacom_workstation_proof(**kwargs)
    kwargs = fixture()
    kwargs["challenge"] = replace(
        kwargs["challenge"], expires_at=NOW + timedelta(seconds=31)
    )
    with pytest.raises(HTTPException):
        verify_enrolled_wacom_workstation_proof(**kwargs)
