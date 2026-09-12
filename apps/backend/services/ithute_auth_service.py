from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
from pydantic_settings import BaseSettings, SettingsConfigDict


class IthuteAuthDisabled(RuntimeError):
    """Raised when central authentication has not been enabled for LoanHub."""


class IthuteAuthUnavailable(RuntimeError):
    """Raised when the central signing-key endpoint cannot be reached."""


class IthuteAuthSettings(BaseSettings):
    enabled: bool = False
    issuer: str = "https://auth.ithute.co.ls"
    audience: str = "loanhub"
    jwks_url: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="ITHUTE_AUTH_",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def resolved_issuer(self) -> str:
        return self.issuer.rstrip("/")

    @property
    def resolved_jwks_url(self) -> str:
        return self.jwks_url or f"{self.resolved_issuer}/.well-known/jwks.json"


@lru_cache(maxsize=1)
def get_ithute_auth_settings() -> IthuteAuthSettings:
    return IthuteAuthSettings()


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    # PyJWKClient caches the JWK set and signing keys in-process. LoanHub never
    # receives or stores the !thute Auth private key.
    return PyJWKClient(url)


def ithute_auth_enabled() -> bool:
    return bool(get_ithute_auth_settings().enabled)


def decode_ithute_access_token(
    token: str,
    *,
    config: IthuteAuthSettings | None = None,
    jwks_client: Any | None = None,
) -> dict[str, Any]:
    """Validate a first-party !thute Auth access token for LoanHub.

    Validation is deliberately strict: RS256 only, exact central issuer,
    exact LoanHub audience, access-token use, and UUID `sub`/`sid` claims.
    Product roles are not trusted from the central token; LoanHub loads them
    from its own database after resolving `sub` to `users.auth_user_id`.
    """

    settings = config or get_ithute_auth_settings()
    if not settings.enabled:
        raise IthuteAuthDisabled("!thute Auth is disabled for LoanHub")

    client = jwks_client or _jwks_client(settings.resolved_jwks_url)
    try:
        signing_key = client.get_signing_key_from_jwt(token).key
    except PyJWKClientConnectionError as error:
        raise IthuteAuthUnavailable("!thute Auth signing keys are unavailable") from error
    except PyJWKClientError as error:
        raise jwt.InvalidTokenError("unknown or invalid !thute Auth signing key") from error

    claims = jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        issuer=settings.resolved_issuer,
        audience=settings.audience,
        options={"require": ["iss", "sub", "aud", "sid", "iat", "nbf", "exp", "token_use"]},
    )
    if claims.get("token_use") != "access":
        raise jwt.InvalidTokenError("wrong !thute Auth token type")

    try:
        UUID(str(claims["sub"]))
        UUID(str(claims["sid"]))
    except (KeyError, TypeError, ValueError) as error:
        raise jwt.InvalidTokenError("invalid !thute Auth identity claims") from error

    return claims
