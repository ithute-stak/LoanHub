from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis
from redis.exceptions import RedisError

from database.config.config import settings
from integrations.cdas_session import CdasSessionBrokerError, CdasSharedSession
from services.crypto_service import decrypt_control_secret, encrypt_control_secret


_SESSION_PURPOSE = b"loanhub-cdas-session-v1"
_SESSION_TTL_SECONDS = 8 * 60 * 60
_LOGIN_LOCK_TTL_SECONDS = 30
_LOGIN_LOCK_WAIT_SECONDS = 25.0
_NAMESPACE = "loanhub:cdas:session:v1"

_redis_client: Redis | None = None


def _redis() -> Redis:
    global _redis_client
    if not settings.REDIS_URL:
        raise CdasSessionBrokerError("Redis is required for shared CDAS session coordination")
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def cdas_session_account_key(username: str, environment: str) -> str:
    normalized = f"{environment.strip().lower()}\0{username.strip().casefold()}".encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


class RedisCdasSessionBroker:
    """Encrypted cross-worker CDAS token/cookie store with a distributed login lock."""

    def __init__(self, *, username: str, environment: str) -> None:
        account_key = cdas_session_account_key(username, environment)
        self._session_key = f"{_NAMESPACE}:{account_key}"
        self._lock_key = f"{self._session_key}:login-lock"

    @staticmethod
    def _encode(session: CdasSharedSession) -> str:
        plaintext = json.dumps(
            {
                "token": session.token,
                "cookies": session.cookies,
                "obtained_at": session.obtained_at.isoformat(),
                "last_used_at": session.last_used_at.isoformat(),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        ciphertext, nonce, version = encrypt_control_secret(plaintext, _SESSION_PURPOSE)
        return json.dumps(
            {"ciphertext": ciphertext, "nonce": nonce, "version": version},
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _decode(value: str) -> CdasSharedSession:
        envelope = json.loads(value)
        plaintext = decrypt_control_secret(
            str(envelope["ciphertext"]),
            str(envelope["nonce"]),
            str(envelope["version"]),
            _SESSION_PURPOSE,
        )
        payload = json.loads(plaintext)
        return CdasSharedSession(
            token=str(payload["token"]),
            cookies={str(key): str(item) for key, item in dict(payload.get("cookies") or {}).items()},
            obtained_at=__import__("datetime").datetime.fromisoformat(str(payload["obtained_at"])),
            last_used_at=__import__("datetime").datetime.fromisoformat(str(payload["last_used_at"])),
        )

    async def load(self) -> CdasSharedSession | None:
        client = _redis()
        try:
            value = await client.get(self._session_key)
        except RedisError as exc:
            raise CdasSessionBrokerError("Redis CDAS session storage is unavailable") from exc
        if not value:
            return None
        try:
            return self._decode(str(value))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            try:
                await client.delete(self._session_key)
            except RedisError:
                pass
            raise CdasSessionBrokerError("Stored CDAS shared session could not be verified") from exc

    async def save(self, session: CdasSharedSession) -> None:
        client = _redis()
        try:
            await client.set(
                self._session_key,
                self._encode(session),
                ex=_SESSION_TTL_SECONDS,
            )
        except RedisError as exc:
            raise CdasSessionBrokerError("Redis CDAS session storage is unavailable") from exc

    async def clear(self) -> None:
        try:
            await _redis().delete(self._session_key)
        except RedisError as exc:
            raise CdasSessionBrokerError("Redis CDAS session storage is unavailable") from exc

    @asynccontextmanager
    async def login_lock(self) -> AsyncIterator[None]:
        client = _redis()
        lock_value = secrets.token_urlsafe(24)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _LOGIN_LOCK_WAIT_SECONDS
        acquired = False

        try:
            while loop.time() < deadline:
                try:
                    acquired = bool(
                        await client.set(
                            self._lock_key,
                            lock_value,
                            nx=True,
                            ex=_LOGIN_LOCK_TTL_SECONDS,
                        )
                    )
                except RedisError as exc:
                    raise CdasSessionBrokerError("Redis CDAS login coordination is unavailable") from exc
                if acquired:
                    break
                await asyncio.sleep(0.1)

            if not acquired:
                raise CdasSessionBrokerError("Timed out waiting for the shared CDAS login lock")

            yield
        finally:
            if acquired:
                release_script = (
                    "if redis.call('get', KEYS[1]) == ARGV[1] then "
                    "return redis.call('del', KEYS[1]) else return 0 end"
                )
                try:
                    await client.eval(release_script, 1, self._lock_key, lock_value)
                except RedisError:
                    # The lock has a short TTL. A release failure must not trigger
                    # another CDAS login or mask an already completed provider call.
                    pass
