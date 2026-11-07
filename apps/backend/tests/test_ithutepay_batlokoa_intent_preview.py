import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from integrations import ithutepay_batlokoa_intent_preview as preview
from integrations.ithutepay_batlokoa_handshake import (
    APPLICATION_ID, COMPANY_ID, MASTER_ID, SHORTCODE,
)

SECRET = "purpose-specific-secret-with-at-least-thirty-two-bytes"


def request_body():
    return preview.prepare_preview_request(
        amount="100.00",
        source_reference="loan_ref_A1234567",
        idempotency_key="collect_req_A123456789",
    )


def good_response():
    return {
        "company_id": COMPANY_ID,
        "merchant_id": MASTER_ID,
        "application_id": APPLICATION_ID,
        "mpesa_shortcode": SHORTCODE,
        "application_status": "inactive",
        "integration_status": "pending_authorization",
        "amount": "100.00",
        "currency": "LSL",
        "operation": "collection",
        "ithutepay_platform_total_fee": "0.00",
        "provider_charges_included": False,
        "financial_posting_enabled": False,
        "provider_execution_enabled": False,
        "idempotency_reserved": False,
        "request_fingerprint": "a" * 64,
    }


def test_hmac_signature_binds_exact_post_body_and_path():
    body = request_body()
    nonce = "test-random-nonce-1234567890AB"
    headers = preview.sign_preview(
        secret=SECRET, timestamp=1794024000, nonce=nonce, body=body,
    )
    canonical = (
        f"1794024000\n{nonce}\nPOST\n{preview.PREVIEW_PATH}\n"
        f"{COMPANY_ID}\n{hashlib.sha256(body).hexdigest()}"
    ).encode()
    expected = hmac.new(SECRET.encode(), canonical, hashlib.sha256).hexdigest()
    assert headers["X-LoanHub-Signature"] == expected
    assert headers["Content-Type"] == "application/json"
    assert headers["X-LoanHub-Company-Id"] == COMPANY_ID


def test_canonicalization_and_nonposting_envelope():
    body = request_body()
    assert body == preview.prepare_preview_request(
        amount="100.00", source_reference="loan_ref_A1234567",
        idempotency_key="collect_req_A123456789",
    )
    assert set(json.loads(body)) == {
        "amount", "currency", "source_reference", "idempotency_key",
    }
    assert "merchant_id" not in json.loads(body)
    assert "company_id" not in json.loads(body)


@pytest.mark.parametrize("changes", [
    {"amount": "0"},
    {"amount": "-10"},
    {"amount": "1.001"},
    {"amount": "NaN"},
    {"amount": "Infinity"},
    {"amount": "not-a-number"},
    {"source_reference": "customer@example.com"},
    {"source_reference": "short"},
    {"idempotency_key": "short"},
])
def test_invalid_inputs_rejected_locally(changes):
    values = {
        "amount": "100.00",
        "source_reference": "loan_ref_A1234567",
        "idempotency_key": "collect_req_A123456789",
    }
    values.update(changes)
    with pytest.raises(preview.BatlokoaPreviewError):
        preview.prepare_preview_request(**values)


@pytest.mark.parametrize("field,invalid", [
    ("company_id", "another-company"),
    ("merchant_id", "another-merchant"),
    ("application_id", "wrong-application"),
    ("application_status", "active"),
    ("mpesa_shortcode", "00000"),
    ("financial_posting_enabled", True),
    ("provider_execution_enabled", True),
    ("idempotency_reserved", True),
    ("provider_charges_included", True),
    ("ithutepay_platform_total_fee", "1.00"),
    ("amount", "101.00"),
    ("request_fingerprint", "malformed"),
])
def test_response_rejects_identity_or_safety_drift(field, invalid):
    data = good_response()
    data[field] = invalid
    with pytest.raises(preview.BatlokoaPreviewError):
        preview.verify_preview_response(data, amount="100.00")


def test_disabled_client_does_not_access_network(monkeypatch):
    monkeypatch.setattr("httpx.Client", lambda **kwargs: (_ for _ in ()).throw(
        AssertionError("Network not allowed when preview is disabled"),
    ))
    with pytest.raises(preview.BatlokoaPreviewError, match="disabled"):
        preview.perform_readonly_collection_preview(
            verified_company_id=COMPANY_ID,
            amount="100.00",
            source_reference="loan_ref_A1234567",
            idempotency_key="collect_req_A123456789",
            enabled=False,
        )


def test_enabled_client_sends_signed_nonposting_request(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen["options"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, content, headers):
            seen["url"] = url
            seen["body"] = content
            seen["headers"] = headers
            return SimpleNamespace(status_code=200, json=good_response)

    monkeypatch.setattr("httpx.Client", FakeClient)
    value = preview.perform_readonly_collection_preview(
        verified_company_id=COMPANY_ID,
        amount="100.00",
        source_reference="loan_ref_A1234567",
        idempotency_key="collect_req_A123456789",
        enabled=True, secret=SECRET,
        base_url="https://api.pay.ithute.co.ls",
    )
    assert value["financial_posting_enabled"] is False
    assert seen["url"].endswith(preview.PREVIEW_PATH)
    assert seen["options"]["follow_redirects"] is False
    assert seen["options"]["trust_env"] is False
    assert set(json.loads(seen["body"])) == {
        "amount", "currency", "source_reference", "idempotency_key",
    }
    assert "X-LoanHub-Signature" in seen["headers"]


@pytest.mark.parametrize("origin", [
    "http://api.pay.ithute.co.ls",
    "https://user:password@api.pay.ithute.co.ls",
    "https://api.pay.ithute.co.ls/elsewhere",
    "https://api.pay.ithute.co.ls?test=true",
])
def test_bad_endpoint_origins_rejected(origin):
    with pytest.raises(preview.BatlokoaPreviewError):
        preview.perform_readonly_collection_preview(
            verified_company_id=COMPANY_ID, amount="100.00",
            source_reference="loan_ref_A1234567",
            idempotency_key="collect_req_A123456789",
            enabled=True, secret=SECRET, base_url=origin,
        )
