from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Final

from fastapi import Request
from redis import asyncio as redis_async
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from database.config.config import settings


_PERIODS: Final[dict[str, int]] = {
    'second': 1,
    'seconds': 1,
    'minute': 60,
    'minutes': 60,
    'hour': 3600,
    'hours': 3600,
    'day': 86400,
    'days': 86400,
}


@dataclass(frozen=True, slots=True)
class RateRule:
    limit: int
    window_seconds: int


def parse_rate_rule(value: str) -> RateRule:
    try:
        raw_limit, raw_period = value.strip().lower().split('/', 1)
        limit = int(raw_limit)
        window = _PERIODS[raw_period]
    except (ValueError, KeyError) as error:
        raise ValueError(f'Invalid rate-limit rule: {value!r}') from error
    if limit < 1:
        raise ValueError('Rate-limit count must be positive')
    return RateRule(limit=limit, window_seconds=window)


class _MemoryLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._buckets: dict[str, tuple[int, float]] = {}

    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        now = time.monotonic()
        async with self._lock:
            count, expires_at = self._buckets.get(key, (0, now + window_seconds))
            if expires_at <= now:
                count, expires_at = 0, now + window_seconds
            count += 1
            self._buckets[key] = (count, expires_at)
            if len(self._buckets) > 20_000:
                self._buckets = {
                    bucket_key: bucket
                    for bucket_key, bucket in self._buckets.items()
                    if bucket[1] > now
                }
            return count, max(1, int(expires_at - now))


_MEMORY_LIMITER = _MemoryLimiter()
_REDIS_CLIENT = None
_REDIS_LOCK = asyncio.Lock()


async def _redis_client():
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if not settings.REDIS_URL:
        return None
    async with _REDIS_LOCK:
        if _REDIS_CLIENT is None:
            _REDIS_CLIENT = redis_async.from_url(
                settings.REDIS_URL,
                encoding='utf-8',
                decode_responses=True,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
            )
    return _REDIS_CLIENT


def _client_identity(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for', '').split(',', 1)[0].strip()
    host = forwarded or (request.client.host if request.client else 'unknown')
    return hashlib.sha256(host.encode('utf-8')).hexdigest()[:24]


def _security_headers(response: Response) -> None:
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'no-referrer')
    response.headers.setdefault(
        'Permissions-Policy',
        'camera=(), microphone=(), geolocation=(), payment=()',
    )
    response.headers.setdefault('Cache-Control', 'no-store' if response.status_code >= 400 else 'private')


class SecurityControlMiddleware(BaseHTTPMiddleware):
    """Apply API security headers and distributed rate limiting.

    Redis is preferred so limits are shared between application replicas. If
    Redis is temporarily unavailable the middleware fails over to a bounded
    in-process limiter, keeping authentication endpoints protected instead of
    failing open.

    CORS preflight requests are deliberately not charged against a caller's
    rate-limit budget. Browsers can issue an OPTIONS request before the real
    credentialed request; counting both would halve the effective login limit
    and can lock an authenticated SPA out while it establishes its session.
    """

    async def dispatch(self, request: Request, call_next):
        if (
            not settings.RATE_LIMIT_ENABLED
            or not request.url.path.startswith('/api/')
            or request.method.upper() == 'OPTIONS'
        ):
            response = await call_next(request)
            _security_headers(response)
            return response

        is_auth = request.url.path.startswith('/api/v1/auth/')
        rule = parse_rate_rule(settings.AUTH_RATE_LIMIT if is_auth else settings.RATE_LIMIT)
        bucket = int(time.time()) // rule.window_seconds
        key = f'loanhub:rate:{"auth" if is_auth else "api"}:{_client_identity(request)}:{bucket}'
        count = 0
        retry_after = rule.window_seconds

        client = await _redis_client()
        if client is not None:
            try:
                pipe = client.pipeline(transaction=True)
                pipe.incr(key)
                pipe.expire(key, rule.window_seconds + 1)
                result = await pipe.execute()
                count = int(result[0])
                ttl = await client.ttl(key)
                retry_after = max(1, int(ttl))
            except Exception:
                count, retry_after = await _MEMORY_LIMITER.increment(key, rule.window_seconds)
        else:
            count, retry_after = await _MEMORY_LIMITER.increment(key, rule.window_seconds)

        if count > rule.limit:
            response = JSONResponse(
                status_code=429,
                content={'detail': 'Too many requests. Try again later.'},
                headers={'Retry-After': str(retry_after)},
            )
            _security_headers(response)
            return response

        response = await call_next(request)
        response.headers['X-RateLimit-Limit'] = str(rule.limit)
        response.headers['X-RateLimit-Remaining'] = str(max(0, rule.limit - count))
        _security_headers(response)
        return response
