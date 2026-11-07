"""Offline HMAC wire contract vectors, not a live network client."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re

COMPANY_ID = "4236a21f-5164-48aa-90f3-a35eccd23ae2"
PATH = "/api/v1/integrations/loanhub/batlokoa/collection-intent-preview"

@dataclass(frozen=True)
class SignedVector:
    body: bytes
    headers: dict[str, str]

def signed_test_vector(*, secret: str, timestamp: int, nonce: str,
                       amount: str, source_reference: str,
                       idempotency_key: str) -> SignedVector:
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("Invalid test secret")
    if not isinstance(source_reference, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", source_reference):
        raise ValueError("Invalid opaque loan reference")
    if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", idempotency_key):
        raise ValueError("Invalid request key")
    if not isinstance(nonce, str) or not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", nonce):
        raise ValueError("Invalid nonce")
    try:
        money = Decimal(amount)
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError("Invalid amount") from exc
    if (not money.is_finite() or money <= 0 or
            money > Decimal("9999999999999999.99") or
            money != money.quantize(Decimal("0.01"))):
        raise ValueError("Invalid LSL cents")
    body = json.dumps({
        "amount": format(money, ".2f"), "currency": "LSL",
        "source_reference": source_reference, "idempotency_key": idempotency_key,
    }, sort_keys=True, separators=(",", ":")).encode()
    canonical = (
        f"{timestamp}\n{nonce}\nPOST\n{PATH}\n{COMPANY_ID}\n"
        f"{hashlib.sha256(body).hexdigest()}"
    ).encode()
    signature = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    return SignedVector(body, {
        "Content-Type": "application/json",
        "X-LoanHub-Company-Id": COMPANY_ID,
        "X-LoanHub-Timestamp": str(timestamp),
        "X-LoanHub-Nonce": nonce,
        "X-LoanHub-Signature": signature,
    })

def verify_test_vector(vector: SignedVector, *, secret: str) -> bool:
    try:
        headers = vector.headers
        if headers["X-LoanHub-Company-Id"] != COMPANY_ID:
            return False
        body_hash = hashlib.sha256(vector.body).hexdigest()
        canonical = (
            f'{headers["X-LoanHub-Timestamp"]}\n'
            f'{headers["X-LoanHub-Nonce"]}\nPOST\n{PATH}\n{COMPANY_ID}\n{body_hash}'
        ).encode()
        actual = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
        return hmac.compare_digest(actual, headers["X-LoanHub-Signature"])
    except (KeyError, TypeError):
        return False
