from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.models.enums import PaymentDirection, PaymentPurpose, PaymentProvider, PaymentStatus
from services.principal_x_gateway_reversal_review import review_gateway_reversals


def evidence():
    company, loan, payment_id = uuid4(), uuid4(), uuid4()
    payment = SimpleNamespace(
        id=payment_id, company_id=company, loan_id=loan,
        provider=PaymentProvider.LELEFAPAYGATE, status=PaymentStatus.REVERSED,
        purpose=PaymentPurpose.LOAN_REPAYMENT, direction=PaymentDirection.INBOUND,
        amount=Decimal("100.00"), currency="LSL", provider_reference="gateway-1",
    )
    event = SimpleNamespace(
        event_id="event-1", event_type="payment.reversed", payment_id=payment_id,
        processing_status="processed", processed_at=datetime(2026, 1, 1),
        processing_error=None, payload_hash="a" * 64,
        payload={"type": "payment.reversed", "data": {
            "id": "gateway-1", "currency": "LSL", "amount": "100.00",
            "metadata": {"loanhub_payment_id": str(payment_id)},
        }},
    )
    return payment, event, dict(company_id=company, loan_id=loan)


def test_consistent_gateway_record_is_not_independent_finality():
    payment, event, scope = evidence()
    result = review_gateway_reversals(payments=[payment], events=[event], **scope)
    assert result.corroborated_payment_count == 1
    assert result.missing_evidence_count == 0
    assert result.complete is False


@pytest.mark.parametrize("problem", [
    "amount_missing", "amount_mismatch", "subcent", "currency_missing",
    "currency_mismatch", "reference", "metadata", "hash", "processing",
    "error", "timestamp", "type",
])
def test_incomplete_gateway_evidence_is_not_corroboration(problem):
    payment, event, scope = evidence()
    data = event.payload["data"]
    if problem == "amount_missing":
        del data["amount"]
    elif problem == "amount_mismatch":
        data["amount"] = "99.99"
    elif problem == "subcent":
        data["amount"] = "100.001"
    elif problem == "currency_missing":
        del data["currency"]
    elif problem == "currency_mismatch":
        data["currency"] = "USD"
    elif problem == "reference":
        data["id"] = "other-gateway"
    elif problem == "metadata":
        data["metadata"]["loanhub_payment_id"] = str(uuid4())
    elif problem == "hash":
        event.payload_hash = "bad"
    elif problem == "processing":
        event.processing_status = "received"
    elif problem == "error":
        event.processing_error = "rejected"
    elif problem == "timestamp":
        event.processed_at = None
    else:
        event.payload["type"] = "payment.succeeded"
    result = review_gateway_reversals(payments=[payment], events=[event], **scope)
    assert result.corroborated_payment_count == 0
    assert result.missing_evidence_count == 1
    assert result.inconsistent_event_count == 1
    assert result.complete is False


def test_duplicate_event_does_not_count_twice():
    payment, event, scope = evidence()
    result = review_gateway_reversals(payments=[payment], events=[event, event], **scope)
    assert result.corroborated_payment_count == 1
    assert result.inconsistent_event_count == 1
    assert result.complete is False


def test_missing_event_requires_review():
    payment, _, scope = evidence()
    result = review_gateway_reversals(payments=[payment], events=[], **scope)
    assert result.missing_evidence_count == 1
    assert result.complete is False


def test_cross_loan_webhook_rejected():
    payment, event, scope = evidence()
    event.payment_id = uuid4()
    with pytest.raises(ValueError):
        review_gateway_reversals(payments=[payment], events=[event], **scope)
