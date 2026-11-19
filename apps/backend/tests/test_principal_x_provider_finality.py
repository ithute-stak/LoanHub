from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payment_engine.principal_x_provider_finality import (
    ProviderFinalityEvidence, require_provider_finality,
)


COMPANY, LOAN = uuid4(), uuid4()
NOW = datetime.now(timezone.utc) - timedelta(minutes=5)


def valid_evidence():
    return ProviderFinalityEvidence(
        company_id=COMPANY, loan_id=LOAN,
        provider="mpesa", provider_reference="provider-001",
        verification_reference="provider-verified-001",
        idempotency_key="payment-001",
        amount=Decimal("500.00"), currency="LSL",
        final_status="succeeded", verified_at=NOW,
        independently_verified=True,
    )


def check(evidence, **overrides):
    arguments = dict(
        evidence=evidence, company_id=COMPANY, loan_id=LOAN,
        expected_amount=Decimal("500.00"),
        expected_provider_reference="provider-001",
        expected_idempotency_key="payment-001",
    )
    arguments.update(overrides)
    return require_provider_finality(**arguments)


def test_matching_verified_provider_evidence_accepted():
    assert check(valid_evidence()) == valid_evidence()


@pytest.mark.parametrize("changes", [
    {"company_id": uuid4()},
    {"loan_id": uuid4()},
    {"provider": ""},
    {"provider_reference": "other"},
    {"verification_reference": ""},
    {"idempotency_key": "other"},
    {"amount": Decimal("499.99")},
    {"amount": Decimal("NaN")},
    {"currency": "USD"},
    {"final_status": "pending"},
    {"final_status": "reversed"},
    {"independently_verified": False},
    {"verified_at": NOW.replace(tzinfo=None)},
    {"verified_at": NOW + timedelta(days=2)},
])
def test_untrusted_or_mismatched_provider_evidence_rejected(changes):
    with pytest.raises(ValueError):
        check(replace(valid_evidence(), **changes))


def test_different_expected_amount_rejected():
    with pytest.raises(ValueError, match="amount"):
        check(valid_evidence(), expected_amount=Decimal("501.00"))
