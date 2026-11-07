"""Synthetic TEST-ONLY HMAC evidence. NOT a live Vodacom/Econet/Golink adapter."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import hmac
import json
import re

class EvidenceError(ValueError):
    pass

@dataclass(frozen=True)
class VerifiedEvidence:
    provider: str
    event_id: str
    operation_id: str
    kind: str
    amount: str
    currency: str
    body_hash: str

def verify_test_provider_evidence(*, raw_body: bytes, supplied_signature: str,
                                  shared_test_key: bytes, expected_provider: str) -> VerifiedEvidence:
    if not isinstance(raw_body, bytes) or not 0 < len(raw_body) <= 4096:
        raise EvidenceError("Invalid body size")
    if (not isinstance(shared_test_key, bytes) or len(shared_test_key) < 32 or
            not isinstance(supplied_signature, str) or
            not re.fullmatch(r"[0-9a-f]{64}", supplied_signature)):
        raise EvidenceError("Invalid evidence parameters")
    expected = hmac.new(shared_test_key, raw_body, sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_signature):
        raise EvidenceError("Signature rejected")
    try:
        value = json.loads(raw_body)
        if not isinstance(value, dict) or set(value) != {
            "provider", "event_id", "operation_id", "kind", "amount", "currency"
        }:
            raise ValueError("Unsupported evidence shape")
        if value["provider"] != expected_provider or value["currency"] != "LSL":
            raise ValueError("Unexpected provider/currency")
        if value["kind"] not in {"settled", "failed", "reversed"}:
            raise ValueError("Unsupported event type")
        for key in ("event_id", "operation_id"):
            if not isinstance(value[key], str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", value[key]):
                raise ValueError("Invalid event identifier")
        if not isinstance(value["amount"], str):
            raise ValueError("Invalid amount type")
        money = Decimal(value["amount"])
        if not money.is_finite() or money <= 0 or money != money.quantize(Decimal("0.01")):
            raise ValueError("Invalid provider amount")
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        raise EvidenceError("Invalid authenticated evidence") from exc
    return VerifiedEvidence(value["provider"], value["event_id"], value["operation_id"],
                            value["kind"], value["amount"], value["currency"], sha256(raw_body).hexdigest())
