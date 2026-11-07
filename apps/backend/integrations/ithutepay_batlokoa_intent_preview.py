"""Disabled-by-default LoanHub client for IthutePay non-posting collection preview.

Only a trusted LoanHub service may call this after verifying borrower/loan
ownership in LoanHub. The preview must never be treated as a payment approval.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import httpx

from database.config.config import settings
from integrations.ithutepay_batlokoa_handshake import (
    APPLICATION_ID, COMPANY_ID, MASTER_ID, SHORTCODE,
    BatlokoaHandshakeError,
)

PREVIEW_PATH = "/api/v1/integrations/loanhub/batlokoa/collection-intent-preview"
REFERENCE_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


class BatlokoaPreviewError(BatlokoaHandshakeError):
    pass


def prepare_preview_request(
    *,
    amount: str | Decimal,
    source_reference: str,
    idempotency_key: str,
    currency: str = "LSL",
) -> bytes:
    """Canonical JSON; opaque references only; no user-supplied merchant ID."""
    if currency != "LSL":
        raise BatlokoaPreviewError("Unsupported currency")
    if not isinstance(source_reference, str) or not REFERENCE_RE.fullmatch(source_reference):
        raise BatlokoaPreviewError("Invalid opaque source reference")
    if not isinstance(idempotency_key, str) or not IDEMPOTENCY_RE.fullmatch(idempotency_key):
        raise BatlokoaPreviewError("Invalid idempotency key")
    try:
        money = Decimal(amount)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BatlokoaPreviewError("Invalid collection amount") from exc
    if not money.is_finite() or money <= 0 or money != money.quantize(Decimal("0.01")):
        raise BatlokoaPreviewError("Amount must be positive LSL cents")
    if len(money.as_tuple().digits) > 18:
        raise BatlokoaPreviewError("Amount exceeds supported precision")
    data = {
        "amount": format(money, ".2f"),
        "currency": currency,
        "source_reference": source_reference,
        "idempotency_key": idempotency_key,
    }
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(raw) > 4096:
        raise BatlokoaPreviewError("Preview request too large")
    return raw


def sign_preview(*, secret: str, timestamp: int, nonce: str, body: bytes) -> dict[str, str]:
    if not isinstance(secret, str) or len(secret) < 32:
        raise BatlokoaPreviewError("Dedicated integration secret missing")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", nonce):
        raise BatlokoaPreviewError("Invalid preview nonce")
    digest = hashlib.sha256(body).hexdigest()
    canonical = (
        f"{timestamp}\n{nonce}\nPOST\n{PREVIEW_PATH}\n{COMPANY_ID}\n{digest}"
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return {
        "X-LoanHub-Company-Id": COMPANY_ID,
        "X-LoanHub-Timestamp": str(timestamp),
        "X-LoanHub-Nonce": nonce,
        "X-LoanHub-Signature": signature,
        "Content-Type": "application/json",
    }


def expected_preview_fingerprint(*, request_body: bytes) -> str:
    """Independently reproduce IthutePay's versioned request fingerprint.

    This confirms the remote preview corresponds to the exact request we
    sent. It is not a payment authorization or an idempotency reservation.
    """
    try:
        payload = json.loads(request_body)
        if not isinstance(payload, dict):
            raise ValueError("Invalid preview request")
        canonical = json.dumps(
            {
                "version": 1,
                "company_id": COMPANY_ID,
                "merchant_id": MASTER_ID,
                "application_id": APPLICATION_ID,
                "operation": "collection",
                "currency": "LSL",
                "amount": payload["amount"],
                "source_reference": payload["source_reference"],
                "idempotency_key": payload["idempotency_key"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (ValueError, KeyError, TypeError) as exc:
        raise BatlokoaPreviewError("Invalid local preview request") from exc
    return hashlib.sha256(canonical).hexdigest()


def verify_preview_response(value: object, *, amount: str, expected_fingerprint: str | None = None) -> dict:
    if not isinstance(value, dict):
        raise BatlokoaPreviewError("Invalid IthutePay preview response")
    expected = {
        "company_id": COMPANY_ID,
        "merchant_id": MASTER_ID,
        "application_id": APPLICATION_ID,
        "mpesa_shortcode": SHORTCODE,
        "application_status": "inactive",
        "integration_status": "pending_authorization",
        "amount": amount,
        "currency": "LSL",
        "operation": "collection",
        "ithutepay_platform_total_fee": "0.00",
        "provider_charges_included": False,
        "financial_posting_enabled": False,
        "provider_execution_enabled": False,
        "idempotency_reserved": False,
    }
    for key, expected_value in expected.items():
        if type(value.get(key)) is not type(expected_value) or value.get(key) != expected_value:
            raise BatlokoaPreviewError("Preview binding or financial safety mismatch")
    fingerprint = value.get("request_fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise BatlokoaPreviewError("Invalid request fingerprint")
    if expected_fingerprint is not None and not hmac.compare_digest(
        fingerprint, expected_fingerprint,
    ):
        raise BatlokoaPreviewError("Preview fingerprint does not match signed request")
    if "source_reference" in value or "idempotency_key" in value:
        raise BatlokoaPreviewError("Preview unexpectedly exposed private request identifiers")
    return {key: value[key] for key in (*expected, "request_fingerprint")}


def perform_readonly_collection_preview(
    *,
    verified_company_id: str,
    amount: str | Decimal,
    source_reference: str,
    idempotency_key: str,
    enabled: bool | None = None,
    secret: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float | None = None,
) -> dict:
    """No borrower lookup is performed here; caller must independently authorize it."""
    if enabled is None:
        enabled = settings.ITHUTEPAY_BATLOKOA_INTENT_PREVIEW_ENABLED
    if not enabled:
        raise BatlokoaPreviewError("Collection-intent preview is disabled")
    if verified_company_id != COMPANY_ID:
        raise BatlokoaPreviewError("Unverified LoanHub company")
    key = secret if secret is not None else settings.ITHUTEPAY_BATLOKOA_HANDSHAKE_SECRET
    endpoint = base_url if base_url is not None else settings.ITHUTEPAY_BATLOKOA_HANDSHAKE_BASE_URL
    url = urlsplit(endpoint)
    if (url.scheme != "https" or not url.netloc or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/")):
        raise BatlokoaPreviewError("Preview requires a dedicated HTTPS origin")
    body = prepare_preview_request(
        amount=amount, source_reference=source_reference,
        idempotency_key=idempotency_key,
    )
    headers = sign_preview(
        secret=key, timestamp=int(time.time()),
        nonce=secrets.token_urlsafe(32), body=body,
    )
    timeout = timeout_seconds if timeout_seconds is not None else settings.ITHUTEPAY_BATLOKOA_HANDSHAKE_TIMEOUT_SECONDS
    if not 0 < timeout <= 15:
        raise BatlokoaPreviewError("Preview timeout out of bounds")
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = client.post(endpoint.rstrip("/") + PREVIEW_PATH, content=body, headers=headers)
    except httpx.RequestError as exc:
        raise BatlokoaPreviewError("IthutePay preview transport failed") from exc
    if response.status_code != 200:
        raise BatlokoaPreviewError(f"IthutePay preview returned HTTP {response.status_code}")
    try:
        value = response.json()
    except ValueError as exc:
        raise BatlokoaPreviewError("IthutePay preview returned invalid JSON") from exc
    return verify_preview_response(
        value,
        amount=json.loads(body)["amount"],
        expected_fingerprint=expected_preview_fingerprint(request_body=body),
    )
