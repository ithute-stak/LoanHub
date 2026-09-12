from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from services.ithute_auth_service import IthuteAuthSettings, decode_ithute_access_token


class StaticJwksClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, _token: str):
        return SimpleNamespace(key=self.public_key)


def _fixture():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    config = IthuteAuthSettings(
        enabled=True,
        issuer="https://auth.ithute.co.ls",
        audience="loanhub",
    )
    now = datetime.now(timezone.utc)
    claims = {
        "iss": "https://auth.ithute.co.ls",
        "sub": str(uuid4()),
        "aud": "loanhub",
        "sid": str(uuid4()),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "token_use": "access",
    }
    return private_key, public_key, config, claims


def _token(private_key, claims: dict) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test"})


def test_accepts_exact_ithute_loanhub_access_token():
    private_key, public_key, config, claims = _fixture()
    decoded = decode_ithute_access_token(
        _token(private_key, claims),
        config=config,
        jwks_client=StaticJwksClient(public_key),
    )
    assert decoded["sub"] == claims["sub"]
    assert decoded["aud"] == "loanhub"
    assert decoded["token_use"] == "access"


def test_rejects_token_for_another_product():
    private_key, public_key, config, claims = _fixture()
    claims["aud"] = "rsl-pos"
    with pytest.raises(jwt.InvalidAudienceError):
        decode_ithute_access_token(
            _token(private_key, claims),
            config=config,
            jwks_client=StaticJwksClient(public_key),
        )


def test_rejects_service_token_as_human_login():
    private_key, public_key, config, claims = _fixture()
    claims["token_use"] = "service"
    with pytest.raises(jwt.InvalidTokenError):
        decode_ithute_access_token(
            _token(private_key, claims),
            config=config,
            jwks_client=StaticJwksClient(public_key),
        )


def test_central_auth_is_opt_in():
    private_key, public_key, _config, claims = _fixture()
    disabled = IthuteAuthSettings(enabled=False)
    with pytest.raises(RuntimeError, match="disabled"):
        decode_ithute_access_token(
            _token(private_key, claims),
            config=disabled,
            jwks_client=StaticJwksClient(public_key),
        )
