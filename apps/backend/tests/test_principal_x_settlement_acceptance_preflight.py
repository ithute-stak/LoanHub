from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payment_engine.principal_x_settlement import PrincipalXQuote
from payment_engine.principal_x_settlement_consent import (
    BorrowerAcceptance, issue_settlement_offer,
)
from services.principal_x_settlement_acceptance_preflight import (
    preflight_principal_x_settlement_acceptance,
)
from services.principal_x_settlement_preview_service import PrincipalXSnapshotQuote


NOW = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)
REVISION = "a" * 64


def example():
    quote = PrincipalXQuote(
        period=2,
        uncapped_due=Decimal("1324.80"),
        collectible_due=Decimal("1324.80"),
        contractual_remaining=Decimal("1392.00"),
        lifetime_cap_remaining=Decimal("2304.00"),
        total_credited=Decimal("696.00"),
        ceiling_reduction=Decimal("0.00"),
    )
    offer = issue_settlement_offer(
        loan_id=uuid4(), company_id=uuid4(), quote=quote,
        issued_at=NOW, expires_at=NOW + timedelta(minutes=20),
        ledger_revision="authoritative-ledger-v1",
    )
    accepted = BorrowerAcceptance(
        loan_id=offer.loan_id, company_id=offer.company_id,
        accepted_amount=Decimal("1324.80"),
        accepted_at=NOW + timedelta(minutes=2),
        ledger_revision="authoritative-ledger-v1",
        verified_identity=True,
        consent_evidence_id="evidence-1",
    )
    return offer, accepted, PrincipalXSnapshotQuote(quote=quote, snapshot_revision=REVISION)


def check(offer, accepted, snapshot, **overrides):
    arguments = dict(
        offer=offer,
        acceptance=accepted,
        current_snapshot=snapshot,
        quoted_snapshot_revision=REVISION,
        authoritative_ledger_revision="authoritative-ledger-v1",
        now=NOW + timedelta(minutes=3),
    )
    arguments.update(overrides)
    return preflight_principal_x_settlement_acceptance(**arguments)


def test_matching_quote_and_verified_acceptance_claims_remain_non_postable():
    offer, accepted, snapshot = example()
    result = check(offer, accepted, snapshot)
    assert result.accepted_amount == Decimal("1324.80")
    assert result.snapshot_revision == REVISION
    assert result.loan_id == offer.loan_id
    assert result.company_id == offer.company_id
    assert result.payment_authorized is False


@pytest.mark.parametrize("change", [
    {"quoted_snapshot_revision": "b" * 64},
    {"authoritative_ledger_revision": "authoritative-ledger-v2"},
    {"now": NOW + timedelta(hours=1)},
])
def test_stale_snapshot_ledger_or_expiry_fails_closed(change):
    offer, accepted, snapshot = example()
    with pytest.raises(ValueError):
        check(offer, accepted, snapshot, **change)


def test_changed_quote_and_accepted_amount_fail_closed():
    offer, accepted, snapshot = example()
    altered = replace(snapshot.quote, collectible_due=Decimal("1324.79"))
    with pytest.raises(ValueError, match="quote amount or components"):
        check(offer, accepted, replace(snapshot, quote=altered))
    with pytest.raises(ValueError, match="Accepted amount"):
        check(offer, replace(accepted, accepted_amount=Decimal("1284.00")), snapshot)


def test_cross_tenant_or_unverified_consent_fails_closed():
    offer, accepted, snapshot = example()
    for invalid in (
        replace(accepted, company_id=uuid4()),
        replace(accepted, verified_identity=False),
        replace(accepted, consent_evidence_id=""),
    ):
        with pytest.raises(ValueError):
            check(offer, invalid, snapshot)
