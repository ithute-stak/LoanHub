from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.company_operating_system import CompanyWebhookEndpoint
from database.models.governance_control import WebhookDeliveryAttempt, WebhookOutboxEvent
from services.crypto_service import decrypt_control_secret


WEBHOOK_SECRET_PURPOSE = b"loanhub-outbound-webhook-v1"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def validate_webhook_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Webhook endpoint must be an HTTP(S) URL without embedded credentials")
    if settings.ENVIRONMENT.lower() == "production" and parsed.scheme != "https":
        raise HTTPException(status_code=422, detail="Production webhook endpoints must use HTTPS")
    if settings.ENVIRONMENT.lower() != "production" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return value
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as error:
        raise HTTPException(status_code=422, detail="Webhook endpoint hostname could not be resolved") from error
    for raw in addresses:
        address = ipaddress.ip_address(raw)
        if address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified:
            raise HTTPException(status_code=422, detail="Webhook endpoint resolves to a non-public address")
    return value


def enqueue_webhook(
    db: Session,
    *,
    company_id: UUID,
    event_type: str,
    payload: dict,
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    idempotency_key: str,
) -> list[WebhookOutboxEvent]:
    endpoints = db.query(CompanyWebhookEndpoint).filter(
        CompanyWebhookEndpoint.company_id == company_id,
        CompanyWebhookEndpoint.is_active.is_(True),
    ).all()
    rows: list[WebhookOutboxEvent] = []
    for endpoint in endpoints:
        if endpoint.event_types and event_type not in endpoint.event_types and "*" not in endpoint.event_types:
            continue
        existing = db.query(WebhookOutboxEvent).filter(
            WebhookOutboxEvent.endpoint_id == endpoint.id,
            WebhookOutboxEvent.idempotency_key == idempotency_key,
        ).first()
        if existing:
            rows.append(existing)
            continue
        row = WebhookOutboxEvent(
            company_id=company_id,
            endpoint_id=endpoint.id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            idempotency_key=idempotency_key,
            payload=payload,
            status="pending",
            next_attempt_at=_now(),
        )
        db.add(row)
        rows.append(row)
    return rows


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _deliver(db: Session, event: WebhookOutboxEvent) -> None:
    endpoint = db.get(CompanyWebhookEndpoint, event.endpoint_id)
    event.attempt_count = int(event.attempt_count or 0) + 1
    event.last_attempt_at = _now()
    started = time.monotonic()
    response_status = None
    response_hash = None
    error_text = None
    try:
        if not endpoint or not endpoint.is_active:
            raise RuntimeError("Webhook endpoint is inactive or missing")
        if not endpoint.encrypted_secret or not endpoint.encryption_nonce or not endpoint.encryption_version:
            raise RuntimeError("Webhook signing secret must be rotated before delivery")
        validate_webhook_url(endpoint.endpoint_url)
        secret = decrypt_control_secret(
            endpoint.encrypted_secret,
            endpoint.encryption_nonce,
            endpoint.encryption_version,
            WEBHOOK_SECRET_PURPOSE,
        )
        body = json.dumps(event.payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        timestamp = str(int(time.time()))
        response = httpx.post(
            endpoint.endpoint_url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "LoanHub-Webhook/1.0",
                "X-LoanHub-Event": event.event_type,
                "X-LoanHub-Event-ID": str(event.id),
                "X-LoanHub-Timestamp": timestamp,
                "X-LoanHub-Signature": _sign(secret, timestamp, body),
            },
            timeout=settings.WEBHOOK_DELIVERY_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
        response_status = response.status_code
        response_hash = hashlib.sha256(response.content[:65536]).hexdigest()
        if 200 <= response.status_code < 300:
            event.status = "delivered"
            event.delivered_at = _now()
            event.last_error = None
            endpoint.failure_count = 0
            endpoint.last_delivery_at = _now()
        else:
            raise RuntimeError(f"Endpoint returned HTTP {response.status_code}")
    except Exception as error:
        error_text = str(error)[:1000]
        event.last_error = error_text
        if event.attempt_count >= settings.WEBHOOK_DELIVERY_MAX_ATTEMPTS:
            event.status = "dead_letter"
        else:
            event.status = "retrying"
            delay = min(3600, 15 * (2 ** max(0, event.attempt_count - 1)))
            event.next_attempt_at = _now() + timedelta(seconds=delay)
        if endpoint:
            endpoint.failure_count = int(endpoint.failure_count or 0) + 1
    finally:
        event.response_status = response_status
        db.add(WebhookDeliveryAttempt(
            outbox_event_id=event.id,
            attempt_number=event.attempt_count,
            request_timestamp=event.last_attempt_at,
            response_status=response_status,
            response_body_hash=response_hash,
            error=error_text,
            duration_ms=int((time.monotonic() - started) * 1000),
        ))
        db.add(event)
        if endpoint:
            db.add(endpoint)


def process_outbox_batch(db: Session) -> int:
    events = db.query(WebhookOutboxEvent).filter(
        WebhookOutboxEvent.status.in_(["pending", "retrying"]),
        WebhookOutboxEvent.next_attempt_at <= _now(),
    ).order_by(WebhookOutboxEvent.next_attempt_at.asc()).with_for_update(skip_locked=True).limit(
        settings.WEBHOOK_DELIVERY_BATCH_SIZE
    ).all()
    for event in events:
        _deliver(db, event)
    db.commit()
    return len(events)


def replay_outbox_event(db: Session, *, event: WebhookOutboxEvent) -> WebhookOutboxEvent:
    if event.status not in {"dead_letter", "delivered"}:
        raise HTTPException(status_code=409, detail="Only delivered or dead-letter events can be replayed")
    event.status = "pending"
    event.attempt_count = 0
    event.next_attempt_at = _now()
    event.delivered_at = None
    event.last_error = None
    event.response_status = None
    db.add(event)
    return event
