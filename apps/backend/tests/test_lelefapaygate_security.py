import hashlib
import hmac
import json

import pytest

from integrations.lelefa_paygate import (
    LelefaPayGateWebhookError,
    request_signature_headers,
    verify_webhook_signature,
)
from services.lelefa_paygate_service import _gateway_status
from database.models.enums import PaymentStatus


def test_request_signature_matches_gateway_canonical_contract():
    body = b'{"amount":"125.00"}'
    headers = request_signature_headers(
        api_key="ipb_test_secret",
        method="POST",
        path="/api/v1/payment-intents",
        body=body,
        timestamp=1785031200,
        nonce="fixed-nonce",
    )
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = (
        "1785031200\nfixed-nonce\nPOST\n/api/v1/payment-intents\n" + body_hash
    ).encode()
    expected = hmac.new(b"ipb_test_secret", canonical, hashlib.sha256).hexdigest()
    assert headers["X-IPB-Signature"] == f"sha256={expected}"
    assert headers["X-IPB-Nonce"] == "fixed-nonce"


def test_webhook_signature_verification_and_replay_window():
    raw = json.dumps({"id": "evt_1"}, separators=(",", ":")).encode()
    stamp = 1785031200
    digest = hmac.new(
        b"whsec_test",
        str(stamp).encode() + b"." + raw,
        hashlib.sha256,
    ).hexdigest()
    header = f"t={stamp},v1={digest}"
    assert verify_webhook_signature(
        raw,
        header,
        "whsec_test",
        tolerance_seconds=300,
        now=stamp + 10,
    ) == stamp
    with pytest.raises(LelefaPayGateWebhookError):
        verify_webhook_signature(
            raw,
            header,
            "whsec_test",
            tolerance_seconds=300,
            now=stamp + 301,
        )


@pytest.mark.parametrize(
    ("gateway_status", "expected"),
    [
        ("succeeded", PaymentStatus.SUCCEEDED),
        ("completed", PaymentStatus.SUCCEEDED),
        ("processing", PaymentStatus.PROCESSING),
        ("unknown", PaymentStatus.PROCESSING),
        ("failed", PaymentStatus.FAILED),
        ("cancelled", PaymentStatus.CANCELLED),
        ("reversed", PaymentStatus.REVERSED),
    ],
)
def test_gateway_status_mapping_is_fail_closed(gateway_status, expected):
    assert _gateway_status(gateway_status) == expected
