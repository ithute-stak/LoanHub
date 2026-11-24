from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payment_engine.principal_x_settlement import PrincipalXQuote
from payment_engine.principal_x_settlement_consent import (
    BorrowerAcceptance, issue_settlement_offer, validate_settlement_acceptance,
)


NOW = datetime(2026, 11, 19, 8, 0, tzinfo=timezone.utc)


def valid_pair():
    quote = PrincipalXQuote(
        period=1, uncapped_due=Decimal("1200.00"),
        collectible_due=Decimal("1200.00"),
        contractual_remaining=Decimal("1392.00"),
        lifetime_cap_remaining=Decimal("2000.00"),
        total_credited=Decimal("0.00"),
        ceiling_reduction=Decimal("0.00"),
    )
    offer = issue_settlement_offer(
        loan_id=uuid4(), company_id=uuid4(), quote=quote,
        issued_at=NOW, expires_at=NOW + timedelta(hours=1),
        ledger_revision="ledger-v1",
    )
    acceptance = BorrowerAcceptance(
        loan_id=offer.loan_id, company_id=offer.company_id,
        accepted_amount=Decimal("1200.00"),
        accepted_at=NOW + timedelta(minutes=2),
        ledger_revision="ledger-v1", verified_identity=True,
        consent_evidence_id="verified-consent-001",
    )
    return offer, acceptance


def test_valid_acceptance():
    offer, acceptance = valid_pair()
    validate_settlement_acceptance(
        offer=offer, acceptance=acceptance,
        current_ledger_revision="ledger-v1", now=NOW + timedelta(minutes=3),
    )


@pytest.mark.parametrize("change", [
    {"accepted_amount": Decimal("1199.99")},
    {"verified_identity": False},
    {"consent_evidence_id": ""},
    {"ledger_revision": "ledger-v2"},
    {"company_id": uuid4()},
    {"loan_id": uuid4()},
    {"accepted_at": NOW - timedelta(minutes=1)},
])
def test_invalid_acceptance_rejected(change):
    offer, acceptance = valid_pair()
    with pytest.raises(ValueError):
        validate_settlement_acceptance(
            offer=offer, acceptance=replace(acceptance, **change),
            current_ledger_revision="ledger-v1",
            now=NOW + timedelta(minutes=3),
        )


def test_expired_offer_rejected():
    offer, acceptance = valid_pair()
    with pytest.raises(ValueError, match="expired"):
        validate_settlement_acceptance(
            offer=offer, acceptance=acceptance,
            current_ledger_revision="ledger-v1",
            now=NOW + timedelta(hours=2),
        )


def test_stale_ledger_rejected():
    offer, acceptance = valid_pair()
    with pytest.raises(ValueError, match="Ledger changed"):
        validate_settlement_acceptance(
            offer=offer, acceptance=acceptance,
            current_ledger_revision="ledger-v2",
            now=NOW + timedelta(minutes=3),
        )


def test_nonfinite_offer_amount_rejected():
    offer, _ = valid_pair()
    with pytest.raises(ValueError):
        issue_settlement_offer(
            loan_id=offer.loan_id, company_id=offer.company_id,
            quote=replace(offer.quote, collectible_due=Decimal("NaN")),
            issued_at=NOW, expires_at=NOW + timedelta(hours=1),
            ledger_revision="ledger-v1",
        )


def test_naive_time_rejected():
    offer, acceptance = valid_pair()
    with pytest.raises(ValueError, match="Timezone-aware"):
        validate_settlement_acceptance(
            offer=offer, acceptance=acceptance,
            current_ledger_revision="ledger-v1",
            now=NOW.replace(tzinfo=None),
        )
