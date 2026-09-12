from __future__ import annotations

import asyncio
import logging
import time
import uuid

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from redis import asyncio as redis_async
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from database.config.config import settings
from database.session import SessionLocal


log = structlog.get_logger('loanhub.http')


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt='iso', utc=True),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get('x-request-id') or uuid.uuid4().hex
        started = time.perf_counter()
        response = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if response is not None:
                response.headers['X-Request-ID'] = request_id
            log.info(
                'http_request',
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                client=(request.client.host if request.client else None),
            )


def _check_database() -> tuple[bool, str | None]:
    db = SessionLocal()
    try:
        db.execute(text('SELECT 1'))
        return True, None
    except Exception as error:
        return False, error.__class__.__name__
    finally:
        db.close()


async def _check_redis() -> tuple[bool, str | None]:
    if not settings.REDIS_URL:
        return False, 'not_configured'
    client = redis_async.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )
    try:
        await client.ping()
        return True, None
    except Exception as error:
        return False, error.__class__.__name__
    finally:
        await client.aclose()


def install_observability(app: FastAPI) -> None:
    configure_logging()
    app.add_middleware(RequestObservabilityMiddleware)

    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=max(0.0, min(1.0, settings.SENTRY_TRACES_SAMPLE_RATE)),
            send_default_pii=False,
        )

    if settings.METRICS_ENABLED:
        Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            excluded_handlers=['/metrics', '/health/live', '/health/ready'],
        ).instrument(app).expose(app, endpoint='/metrics', include_in_schema=False)

    @app.get('/health/live', include_in_schema=False)
    async def health_live():
        return {'status': 'ok', 'service': 'loanhub-api'}

    @app.get('/health/ready', include_in_schema=False)
    async def health_ready():
        db_ok, db_error = await asyncio.to_thread(_check_database)
        redis_ok, redis_error = await _check_redis()
        payload = {
            'status': 'ready' if db_ok else 'unavailable',
            'database': {'status': 'ok' if db_ok else 'down'},
            'redis': {
                'status': 'ok' if redis_ok else 'degraded',
                'optional': True,
            },
        }
        if settings.ENVIRONMENT.lower() != 'production':
            if db_error:
                payload['database']['error_class'] = db_error
            if redis_error:
                payload['redis']['error_class'] = redis_error
        return JSONResponse(payload, status_code=200 if db_ok else 503)
