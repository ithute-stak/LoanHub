import hashlib
import hmac
from types import SimpleNamespace

import pytest

from integrations.ithutepay_batlokoa_handshake import (
    APPLICATION_ID, COMPANY_ID, HANDSHAKE_PATH, MASTER_ID, SHORTCODE,
    BatlokoaHandshakeError, perform_readonly_handshake,
    sign_handshake, verify_response,
)


def valid_response():
    return {
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


def test_signatures_match_ithutepay_canonical_format():
    secret = "a" * 64
    nonce = "a-valid-random-nonce-1234567890"
    headers = sign_handshake(
        secret=secret, company_id=COMPANY_ID, timestamp=1794024000, nonce=nonce,
    )
    canonical = f"1794024000\n{nonce}\nGET\n{HANDSHAKE_PATH}\n{COMPANY_ID}".encode()
    expected = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    assert headers["X-LoanHub-Signature"] == expected
    assert headers["X-LoanHub-Company-Id"] == COMPANY_ID


@pytest.mark.parametrize("field,wrong", [
    ("company_id", "other-company"),
    ("application_id", "wrong-app"),
    ("merchant_id", "wrong-master"),
    ("mpesa_shortcode", "000000"),
    ("application_status", "active"),
    ("payment_routing_enabled", True),
    ("shared_custody_enabled", True),
    ("fee_enforcement_enabled", True),
])
def test_response_rejects_identity_or_financial_state_drift(field, wrong):
    data = valid_response()
    data[field] = wrong
    with pytest.raises(BatlokoaHandshakeError):
        verify_response(data)


def test_disabled_by_default_cannot_call_network(monkeypatch):
    def disallow_network(*args, **kwargs):
        raise AssertionError("network should not be called")
    monkeypatch.setattr("httpx.Client", disallow_network)
    with pytest.raises(BatlokoaHandshakeError, match="disabled"):
        perform_readonly_handshake(
            company_id=COMPANY_ID, enabled=False, secret="x" * 40,
        )


def test_enabled_handshake_is_readonly_and_verifies_response(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen["client_options"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, headers):
            seen["url"] = url
            seen["headers"] = headers
            return SimpleNamespace(status_code=200, json=valid_response)

    monkeypatch.setattr("httpx.Client", FakeClient)
    assert perform_readonly_handshake(
        company_id=COMPANY_ID, enabled=True,
        secret="x" * 40, base_url="https://api.pay.ithute.co.ls",
        timeout_seconds=5,
    ) == valid_response()
    assert seen["url"].endswith(HANDSHAKE_PATH)
    assert seen["client_options"]["follow_redirects"] is False
    assert seen["client_options"]["trust_env"] is False


@pytest.mark.parametrize("origin", [
    "http://api.pay.ithute.co.ls",
    "https://user:pass@api.pay.ithute.co.ls",
    "https://api.pay.ithute.co.ls/redirect",
    "https://api.pay.ithute.co.ls?bad=1",
])
def test_only_https_origin_is_allowed(origin):
    with pytest.raises(BatlokoaHandshakeError):
        perform_readonly_handshake(
            company_id=COMPANY_ID, enabled=True,
            secret="x" * 40, base_url=origin,
        )
