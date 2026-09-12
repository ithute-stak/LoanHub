from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Any
from urllib.parse import urlencode

from fastapi import Request

try:
    from redis.asyncio import Redis
except ImportError:  # Redis is optional in local/unit-test environments.
    Redis = None  # type: ignore[assignment,misc]

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from database.config.config import settings
from utils.convex import current_user_id


logger = logging.getLogger("loanhub.response_cache")

_CACHEABLE_METHODS = {"GET", "HEAD"}
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PUBLIC_CACHE_PATHS = {
    "/api/v1/billing/plans",
    "/api/v1/loan-products/public",
}
_EXCLUDED_PATH_PARTS = (
    "/auth/",
    "/notifications",
    "/chat/",
    "/system-errors",
    "/ws",
    "/files/",
    "/payroll",
    "/financial-profile",
    "/banking",
    "/credentials",
    "/secrets",
    "/download",
    "/receipt",
    "/pdf",
    "/export",
)


@dataclass(frozen=True)
class ResponseCachePolicy:
    ttl_seconds: int


def response_cache_policy(path: str) -> ResponseCachePolicy:
    normalized = path.lower()

    if any(
        part in normalized
        for part in (
            "/payments",
            "/loans",
            "/collections",
            "/marketplace",
            "/accounting",
            "/finance",
        )
    ):
        return ResponseCachePolicy(ttl_seconds=10)

    if any(
        part in normalized
        for part in (
            "/dashboard",
            "/analytics",
            "/summary",
            "/overview",
            "/workspace",
            "/reports",
        )
    ):
        return ResponseCachePolicy(ttl_seconds=20)

    if any(
        part in normalized
        for part in (
            "/branches",
            "/companies",
            "/employees",
            "/staff",
            "/clients",
            "/borrowers",
            "/candidates",
            "/assets",
        )
    ):
        return ResponseCachePolicy(ttl_seconds=60)

    if any(
        part in normalized
        for part in (
            "/plans",
            "/products",
            "/departments",
            "/positions",
            "/shifts",
            "/leave/types",
            "/settings",
            "/config",
        )
    ):
        return ResponseCachePolicy(ttl_seconds=300)

    return ResponseCachePolicy(
        ttl_seconds=settings.HTTP_CACHE_DEFAULT_TTL_SECONDS,
    )


def _normalized_query(request: Request) -> str:
    return urlencode(sorted(request.query_params.multi_items()), doseq=True)


def _request_identity(request: Request) -> tuple[str, str]:
    user_id = current_user_id.get() or "anonymous"
    company_id = request.headers.get("X-Company-ID") or "platform"
    active_role = request.headers.get("X-Active-Role") or "default"

    if company_id != "platform":
        generation_scope = f"company:{company_id}"
    elif user_id != "anonymous":
        generation_scope = f"user:{user_id}"
    else:
        generation_scope = "public"

    identity = f"{user_id}:{company_id}:{active_role}"
    return identity, generation_scope


def _is_public_cache_path(path: str) -> bool:
    return path.rstrip("/") in {value.rstrip("/") for value in _PUBLIC_CACHE_PATHS}


def _request_is_cacheable(request: Request) -> bool:
    if request.method not in _CACHEABLE_METHODS:
        return False
    if not request.url.path.startswith("/api/v1"):
        return False
    if any(part in request.url.path for part in _EXCLUDED_PATH_PARTS):
        return False

    request_cache_control = request.headers.get("Cache-Control", "").lower()
    loanhub_cache_control = request.headers.get("X-LoanHub-Cache", "").lower()
    if "no-store" in request_cache_control or loanhub_cache_control == "bypass":
        return False

    user_id = current_user_id.get()
    return bool(user_id) or _is_public_cache_path(request.url.path)


def _response_is_cacheable(response: Response, body: bytes) -> bool:
    if response.status_code != 200:
        return False
    if len(body) > settings.HTTP_CACHE_MAX_BODY_BYTES:
        return False

    content_type = response.headers.get("content-type", "").lower()
    cache_control = response.headers.get("cache-control", "").lower()

    return (
        "application/json" in content_type
        and "no-store" not in cache_control
        and "set-cookie" not in response.headers
        and "content-disposition" not in response.headers
    )


def _safe_response_headers(response: Response) -> dict[str, str]:
    allowed = {
        "content-type",
        "content-language",
        "etag",
        "last-modified",
        "vary",
    }
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() in allowed
    }


class RedisResponseCache:
    def __init__(self) -> None:
        self._redis: Any | None = None
        self._retry_after = 0.0

    async def _client(self) -> Any | None:
        if (
            Redis is None
            or not settings.HTTP_CACHE_ENABLED
            or not settings.REDIS_URL
        ):
            return None
        if monotonic() < self._retry_after:
            return None
        if self._redis is not None:
            return self._redis

        try:
            client = Redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.75,
                health_check_interval=30,
            )
            await client.ping()
            self._redis = client
            return client
        except Exception:
            logger.warning("Redis response cache is unavailable", exc_info=True)
            self._retry_after = monotonic() + 10.0
            return None

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    def generation_key(self, generation_scope: str) -> str:
        return (
            f"{settings.HTTP_CACHE_NAMESPACE}:generation:"
            f"{generation_scope}"
        )

    async def generation(self, generation_scope: str) -> int:
        client = await self._client()
        if client is None:
            return 0
        try:
            value = await client.get(self.generation_key(generation_scope))
            return int(value or 0)
        except Exception:
            logger.debug("Could not read cache generation", exc_info=True)
            return 0

    async def bump_generation(self, generation_scope: str) -> None:
        client = await self._client()
        if client is None:
            return
        try:
            key = self.generation_key(generation_scope)
            pipeline = client.pipeline(transaction=False)
            pipeline.incr(key)
            pipeline.expire(key, 7 * 24 * 60 * 60)
            await pipeline.execute()
        except Exception:
            logger.debug("Could not invalidate response cache", exc_info=True)

    def response_key(
        self,
        *,
        request: Request,
        identity: str,
        generation: int,
    ) -> str:
        raw = "|".join(
            (
                request.method,
                request.url.path,
                _normalized_query(request),
                identity,
                str(generation),
            )
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{settings.HTTP_CACHE_NAMESPACE}:response:{digest}"

    async def get(self, key: str) -> dict[str, Any] | None:
        client = await self._client()
        if client is None:
            return None
        try:
            raw = await client.get(key)
            if not raw:
                return None
            value = json.loads(raw)
            return value if isinstance(value, dict) else None
        except Exception:
            logger.debug("Could not read cached response", exc_info=True)
            return None

    async def set(
        self,
        key: str,
        *,
        response: Response,
        body: bytes,
        ttl_seconds: int,
    ) -> None:
        client = await self._client()
        if client is None:
            return
        try:
            payload = {
                "status_code": response.status_code,
                "headers": _safe_response_headers(response),
                "body": body.decode("utf-8"),
            }
            await client.set(
                key,
                json.dumps(payload, separators=(",", ":")),
                ex=max(1, ttl_seconds),
            )
        except Exception:
            logger.debug("Could not store cached response", exc_info=True)


response_cache = RedisResponseCache()


class TenantResponseCacheMiddleware(BaseHTTPMiddleware):
    """Cache safe tenant-scoped JSON reads and invalidate them after writes.

    PostgreSQL remains the source of truth. Redis is an optional cache: any
    Redis failure falls through to the normal request path without failing the
    business operation.
    """

    async def dispatch(self, request: Request, call_next):
        identity, generation_scope = _request_identity(request)

        if _request_is_cacheable(request):
            generation = await response_cache.generation(generation_scope)
            key = response_cache.response_key(
                request=request,
                identity=identity,
                generation=generation,
            )
            cached = await response_cache.get(key)
            if cached is not None:
                headers = dict(cached.get("headers") or {})
                headers["X-LoanHub-Server-Cache"] = "HIT"
                return Response(
                    content=str(cached.get("body") or ""),
                    status_code=int(cached.get("status_code") or 200),
                    headers=headers,
                )

            response = await call_next(request)
            body = b"".join([chunk async for chunk in response.body_iterator])
            headers = dict(response.headers)
            headers["X-LoanHub-Server-Cache"] = "MISS"
            rebuilt = Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                background=response.background,
            )

            if _response_is_cacheable(rebuilt, body):
                await response_cache.set(
                    key,
                    response=rebuilt,
                    body=body,
                    ttl_seconds=response_cache_policy(
                        request.url.path,
                    ).ttl_seconds,
                )
            return rebuilt

        response = await call_next(request)
        response.headers["X-LoanHub-Server-Cache"] = "BYPASS"

        if (
            request.method in _MUTATING_METHODS
            and 200 <= response.status_code < 400
            and request.url.path.startswith("/api/v1")
        ):
            await response_cache.bump_generation(generation_scope)

        return response
