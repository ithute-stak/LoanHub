"""Public HTTP boundary is authenticated and rejects untrusted identity fields."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from routers.batlokoa_collection_preview import (
    BatlokoaPreviewInput, router,
)


def test_anonymous_collection_preview_is_rejected():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    response = TestClient(app).post(
        "/api/v1/loans/00000000-0000-4000-8000-000000000005/batlokoa/collection-preview",
        json={"amount": "100.00", "idempotency_key": "collect_req_A123456789"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("field", [
    "company_id", "borrower_id", "borrower_user_id", "merchant_id",
    "shortcode", "payer_phone", "provider", "payment_execution_enabled",
])
def test_request_cannot_override_identity_or_payment_flags(field):
    with pytest.raises(ValidationError):
        BatlokoaPreviewInput(
            amount="100.00",
            idempotency_key="collect_req_A123456789",
            **{field: "attacker-controlled"},
        )


@pytest.mark.parametrize("amount", ["0", "-1", "1.001"])
def test_invalid_amount_validation(amount):
    with pytest.raises(ValidationError):
        BatlokoaPreviewInput(
            amount=amount,
            idempotency_key="collect_req_A123456789",
        )
