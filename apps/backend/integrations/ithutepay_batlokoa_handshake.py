"""Disabled-by-default read-only LoanHub -> IthutePay Batlokoa handshake.

No application API key, merchant shortcode routing, payment, payout or fee
posting is changed by this integration. Secret is supplied only at runtime.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit

import httpx

from database.config.config import settings

COMPANY_ID = "4236a21f-5164-48aa-90f3-a35eccd23ae2"
MASTER_ID = "3cc13734-5cd3-4ab4-9e4b-d378b715fa3f"
APPLICATION_ID = "153b9348-e9f1-4115-9bd5-48fa761b48b8"
SHORTCODE = "38542"
HANDSHAKE_PATH = "/api/v1/integrations/loanhub/batlokoa/handshake"


class BatlokoaHandshakeError(RuntimeError):
    pass


def sign_handshake(
    *,
    secret: str,
    company_id: str,
    timestamp: int,
    nonce: str,
) -> dict[str, str]:
    if len(secret) < 32:
        raise BatlokoaHandshakeError("Dedicated handshake secret is missing or too short")
    if company_id != COMPANY_ID:
        raise BatlokoaHandshakeError("Unexpected LoanHub company")
    canonical = (
        f"{timestamp}\n{nonce}\nGET\n{HANDSHAKE_PATH}\n{company_id}"
    ).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return {
        "X-LoanHub-Company-Id": company_id,
        "X-LoanHub-Timestamp": str(timestamp),
        "X-LoanHub-Nonce": nonce,
        "X-LoanHub-Signature": digest,
    }


def verify_response(data: object) -> dict:
    if not isinstance(data, dict):
        raise BatlokoaHandshakeError("Invalid IthutePay handshake response")
    expected = {
        "integration": "loanhub-batlokoa",
        "authenticated": True,
        "company_id": COMPANY_ID,
        "application_id": APPLICATION_ID,
        "merchant_id": MASTER_ID,
        "mpesa_shortcode": SHORTCODE,
        "application_status": "inactive",
        "payment_routing_enabled": False,
        "shared_custody_enabled": False,
        "fee_enforcement_enabled": False,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise BatlokoaHandshakeError("IthutePay handshake binding or safety flags mismatch")
    return {key: data[key] for key in expected}


def perform_readonly_handshake(
    *,
    company_id: str,
    base_url: str | None = None,
    secret: str | None = None,
    enabled: bool | None = None,
    timeout_seconds: float | None = None,
) -> dict:
    if enabled is None:
        enabled = settings.ITHUTEPAY_BATLOKOA_HANDSHAKE_ENABLED
    if not enabled:
        raise BatlokoaHandshakeError("Batlokoa handshake is disabled")
    if company_id != COMPANY_ID:
        raise BatlokoaHandshakeError("Unknown LoanHub company")
    key = secret if secret is not None else settings.ITHUTEPAY_BATLOKOA_HANDSHAKE_SECRET
    endpoint = base_url if base_url is not None else settings.ITHUTEPAY_BATLOKOA_HANDSHAKE_BASE_URL
    url = urlsplit(endpoint)
    if (url.scheme != "https" or not url.netloc or url.username or url.password
            or url.query or url.fragment or (url.path not in ("", "/"))):
        raise BatlokoaHandshakeError("Handshake requires a dedicated HTTPS origin")
    nonce = secrets.token_urlsafe(32)
    headers = sign_handshake(
        secret=key, company_id=company_id, timestamp=int(time.time()), nonce=nonce,
    )
    timeout = timeout_seconds if timeout_seconds is not None else settings.ITHUTEPAY_BATLOKOA_HANDSHAKE_TIMEOUT_SECONDS
    if not 0 < timeout <= 15:
        raise BatlokoaHandshakeError("Handshake timeout out of bounds")
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = client.get(endpoint.rstrip("/") + HANDSHAKE_PATH, headers=headers)
    except httpx.RequestError as exc:
        raise BatlokoaHandshakeError("IthutePay handshake transport failed") from exc
    if response.status_code != 200:
        raise BatlokoaHandshakeError(f"IthutePay handshake returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise BatlokoaHandshakeError("IthutePay handshake returned invalid JSON") from exc
    return verify_response(payload)
