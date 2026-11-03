from decimal import Decimal

import pytest

from payment_engine.settlement import (
    SettlementComponents, VerifiedInterestLimit, preview_settlement,
)


def claim(**changes):
    values = dict(
        original_principal=Decimal("1000"),
        principal_collectible=Decimal("1000"),
        ordinary_interest_collectible=Decimal("1200"),
        additional_interest_collectible=Decimal("0"),
        permitted_fees_collectible=Decimal("0"),
        total_historical_paid=Decimal("600"),
    )
    values.update(changes)
    return SettlementComponents(**values)


def test_twice_principal_is_review_signal_not_automatic_settlement():
    preview = preview_settlement(components=claim(total_historical_paid=Decimal("2000")))
    assert preview.twice_original_principal_reached
    assert preview.outstanding == Decimal("200.00")
    assert preview.state == "outstanding"


def test_verified_interest_cap_reduces_collectible_amount_only():
    preview = preview_settlement(
        components=claim(total_historical_paid=Decimal("2000")),
        interest_limit=VerifiedInterestLimit(
            maximum_collectible_interest=Decimal("1000"),
            legal_basis_reference="verified-contract-and-legal-review",
            verified=True,
        ),
    )
    assert preview.collectible_obligation == Decimal("2000.00")
    assert preview.interest_reduction == Decimal("200.00")
    assert preview.state == "settled"
    assert preview.outstanding == Decimal("0.00")


def test_overcharge_remains_explicit_for_refund_reconciliation():
    preview = preview_settlement(
        components=claim(total_historical_paid=Decimal("2500")),
        interest_limit=VerifiedInterestLimit(
            maximum_collectible_interest=Decimal("1000"), legal_basis_reference="approved", verified=True,
        ),
    )
    assert preview.overpayment_for_reconciliation == Decimal("500.00")
    assert preview.state == "overpaid"


@pytest.mark.parametrize("limit", [
    VerifiedInterestLimit(Decimal("1000"), "reviewed", False),
    VerifiedInterestLimit(Decimal("1000"), "", True),
    VerifiedInterestLimit(Decimal("-1"), "reviewed", True),
])
def test_unverified_or_invalid_limit_is_rejected(limit):
    with pytest.raises(ValueError, match="verified legal"):
        preview_settlement(components=claim(), interest_limit=limit)


def test_invalid_negative_payments_or_excess_principal_rejected():
    with pytest.raises(ValueError):
        preview_settlement(components=claim(total_historical_paid=Decimal("-1")))
    with pytest.raises(ValueError):
        preview_settlement(components=claim(principal_collectible=Decimal("1001")))


def test_claim_less_paid_equals_outstanding_plus_net_excess():
    for paid in ("0", "1500", "2200", "3000"):
        result = preview_settlement(components=claim(total_historical_paid=Decimal(paid)))
        assert result.collectible_obligation - result.total_paid == (
            result.outstanding - result.overpayment_for_reconciliation
        )
