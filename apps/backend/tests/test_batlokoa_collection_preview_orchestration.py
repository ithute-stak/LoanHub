"""Non-posting collection-preview orchestration regression tests."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from integrations.ithutepay_batlokoa_handshake import COMPANY_ID
from services import batlokoa_collection_preview_orchestration as service

COMPANY = UUID(COMPANY_ID)
LOAN = UUID("00000000-0000-4000-8000-000000000005")
BORROWER = UUID("00000000-0000-4000-8000-000000000007")


class ReadOnlyDB:
    def scalar(self, statement):
        return BORROWER

    def add(self, *args, **kwargs):
        raise AssertionError("Preview must not insert anything")

    def commit(self):
        raise AssertionError("Preview must not commit")


@pytest.fixture
def valid_context():
    return SimpleNamespace(
        is_platform_admin=False,
        company_id=COMPANY,
        staff=SimpleNamespace(is_active=True),
    )


@pytest.fixture
def approved(monkeypatch):
    monkeypatch.setattr(
        service.settings, "ITHUTEPAY_BATLOKOA_INTENT_PREVIEW_ENABLED", True,
    )

    def authorize(**kwargs):
        assert kwargs["borrower_user_id"] == BORROWER
        return SimpleNamespace(
            company_id=COMPANY_ID, amount="100.00",
            source_reference="loan_" + LOAN.hex,
            payment_execution_enabled=False,
        )

    monkeypatch.setattr(service, "authorize_batlokoa_collection_preview", authorize)
    return service


def invoke(context, db=None, key="collect_req_A123456789"):
    return service.prepare_verified_batlokoa_collection_preview(
        db=db if db is not None else ReadOnlyDB(),
        context=context, loan_id=LOAN,
        amount=Decimal("100.00"), idempotency_key=key,
    )


def test_disabled_gate_does_not_query_or_call_network(monkeypatch, valid_context):
    monkeypatch.setattr(
        service.settings, "ITHUTEPAY_BATLOKOA_INTENT_PREVIEW_ENABLED", False,
    )

    class NoReads:
        def scalar(self, query):
            raise AssertionError("Disabled preview must not read DB")

    with pytest.raises(HTTPException) as exc:
        invoke(valid_context, db=NoReads())
    assert exc.value.status_code == 404


def test_verified_loan_routes_only_to_nonposting_signed_preview(approved, monkeypatch, valid_context):
    calls = []

    def quote(**kwargs):
        calls.append(kwargs)
        return {
            "request_fingerprint": "a" * 64,
            "ithutepay_platform_total_fee": "0.00",
            "provider_charges_included": False,
            "financial_posting_enabled": False,
            "provider_execution_enabled": False,
            "idempotency_reserved": False,
        }

    monkeypatch.setattr(service, "perform_readonly_collection_preview", quote)
    result = invoke(valid_context)
    assert len(calls) == 1
    assert calls[0]["verified_company_id"] == COMPANY_ID
    assert calls[0]["source_reference"] == "loan_" + LOAN.hex
    assert calls[0]["amount"] == "100.00"
    assert result["preview_only"] is True
    assert result["financial_posting_enabled"] is False
    assert result["provider_execution_enabled"] is False
    assert result["idempotency_reserved"] is False
    assert "idempotency_key" not in result
    assert "borrower_user_id" not in result


@pytest.mark.parametrize("change", ["platform", "wrong_company", "staff_missing"])
def test_scope_fails_before_network(approved, monkeypatch, valid_context, change):
    monkeypatch.setattr(
        service, "perform_readonly_collection_preview",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("No network")),
    )
    if change == "platform":
        valid_context.is_platform_admin = True
    elif change == "wrong_company":
        valid_context.company_id = UUID("00000000-0000-4000-8000-000000000099")
    else:
        valid_context.staff = None
    with pytest.raises(HTTPException) as exc:
        invoke(valid_context)
    assert exc.value.status_code == 403


def test_invalid_key_is_rejected(approved, valid_context):
    with pytest.raises(HTTPException) as exc:
        invoke(valid_context, key="short")
    assert exc.value.status_code == 422


def test_rejects_unsafe_upstream_response(approved, monkeypatch, valid_context):
    monkeypatch.setattr(service, "perform_readonly_collection_preview", lambda **kw: {
        "request_fingerprint": "a" * 64,
        "ithutepay_platform_total_fee": "0.00",
        "provider_charges_included": False,
        "financial_posting_enabled": True,
        "provider_execution_enabled": False,
        "idempotency_reserved": False,
    })
    with pytest.raises(HTTPException) as exc:
        invoke(valid_context)
    assert exc.value.status_code == 502


def test_nonexistent_loan_not_sent_upstream(approved, monkeypatch, valid_context):
    class Missing:
        def scalar(self, statement):
            return None

    monkeypatch.setattr(
        service, "perform_readonly_collection_preview",
        lambda **kw: (_ for _ in ()).throw(AssertionError("No network")),
    )
    with pytest.raises(HTTPException) as exc:
        invoke(valid_context, db=Missing())
    assert exc.value.status_code == 404


def test_provider_failure_does_not_expose_upstream_details(approved, monkeypatch, valid_context):
    def unavailable(**kwargs):
        raise service.BatlokoaPreviewError("internal authentication failure detail")
    monkeypatch.setattr(service, "perform_readonly_collection_preview", unavailable)
    with pytest.raises(HTTPException) as exc:
        invoke(valid_context)
    assert exc.value.status_code == 502
    assert "authentication" not in exc.value.detail
