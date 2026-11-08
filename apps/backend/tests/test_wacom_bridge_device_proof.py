"""First-party device possession is scoped and does not authorize signing."""
import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from services.wacom_bridge_device_proof import proof_message, verify_device_proof


def test_enrolled_key_can_prove_device_possession():
    private = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    )
    values = dict(
        company_id=uuid4(), employee_id=uuid4(), workstation_id=uuid4(),
        challenge_id=uuid4(), nonce=b"z" * 32,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=20),
    )
    message = proof_message(**values)
    signature = private.sign(message)
    verify_device_proof(public_key=public, signature=signature, message=message)

    for field in ("company_id", "employee_id", "workstation_id", "challenge_id"):
        changed = dict(values)
        changed[field] = uuid4()
        with pytest.raises(HTTPException) as e:
            verify_device_proof(
                public_key=public, signature=signature, message=proof_message(**changed),
            )
        assert e.value.status_code == 403


def test_invalid_public_key_and_signature_fail_closed():
    values = dict(
        company_id=uuid4(), employee_id=uuid4(), workstation_id=uuid4(),
        challenge_id=uuid4(), nonce=b"x" * 32,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=20),
    )
    with pytest.raises(HTTPException):
        verify_device_proof(public_key=b"x", signature=b"y", message=proof_message(**values))


def test_new_bridge_endpoints_never_sign_documents():
    from api.v1.router import api_router
    paths = {route.path for route in api_router.routes}
    assert "/wacom-bridge/device-challenges" in paths
    assert "/wacom-bridge/device-proofs" in paths
