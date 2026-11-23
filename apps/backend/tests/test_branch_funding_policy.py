"""Isolated tests for offline branch funding policy (not production posting)."""
from decimal import Decimal

import pytest

from services.branch_funding_policy import (
    BranchFundingPolicy,
    FundingRejected,
    OpeningMode,
    opening_is_authorized,
    require_available_funds,
)


def test_manual_opening_is_default():
    assert BranchFundingPolicy().opening_mode == OpeningMode.MANUAL
    assert not opening_is_authorized(policy=BranchFundingPolicy(), manually_confirmed=False)
    assert opening_is_authorized(policy=BranchFundingPolicy(), manually_confirmed=True)


def test_explicit_carry_forward_policy():
    policy = BranchFundingPolicy(opening_mode=OpeningMode.PREVIOUS_CLOSING)
    assert opening_is_authorized(policy=policy, manually_confirmed=False)


@pytest.mark.parametrize("requested", ["3000", "2500.01"])
def test_insufficient_funds_rejected(requested):
    with pytest.raises(FundingRejected, match="Insufficient"):
        require_available_funds(opening_confirmed=True, available="2500", requested=requested)


def test_expense_and_disbursement_share_same_funding_rule():
    assert require_available_funds(opening_confirmed=True, available="4500", requested="1000") == Decimal("3500.00")


def test_reserved_funds_cannot_be_spent_twice():
    with pytest.raises(FundingRejected, match="Insufficient"):
        require_available_funds(opening_confirmed=True, available="5000", reserved="4000", requested="1001")


def test_missing_opening_rejected():
    with pytest.raises(FundingRejected, match="opening"):
        require_available_funds(opening_confirmed=False, available="5000", requested="100")


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "1.001", "0"])
def test_invalid_debits_rejected(bad):
    with pytest.raises(FundingRejected):
        require_available_funds(opening_confirmed=True, available="5000", requested=bad)


def test_debit_requires_tenant_branch_and_channel():
    from services.branch_funding_policy import assert_branch_channel_debit

    for company, branch, channel in [("", "b", "cash"), ("c", "", "cash"), ("c", "b", "")]:
        with pytest.raises(FundingRejected, match="required"):
            assert_branch_channel_debit(
                company_id=company, branch_id=branch, channel=channel,
                opening_confirmed=True, available="100", debit="10",
            )


def test_channel_debit_honors_reservations():
    from services.branch_funding_policy import assert_branch_channel_debit

    with pytest.raises(FundingRejected, match="Insufficient"):
        assert_branch_channel_debit(
            company_id="c", branch_id="b", channel="cash",
            opening_confirmed=True, available="100", reserved="90", debit="11",
        )


def test_pending_gateway_reservation_reduces_available_cash_channel_funds():
    assert require_available_funds(
        opening_confirmed=True, available="5000", reserved="3000", requested="2000"
    ) == Decimal("0.00")
    with pytest.raises(FundingRejected, match="Insufficient"):
        require_available_funds(
            opening_confirmed=True, available="5000", reserved="3000", requested="2000.01"
        )


def test_confirmed_zero_opening_does_not_authorize_positive_debit():
    with pytest.raises(FundingRejected, match="Insufficient"):
        require_available_funds(
            opening_confirmed=True, available="0.00", requested="0.01"
        )


def test_failed_gateway_reservation_can_be_released():
    assert require_available_funds(
        opening_confirmed=True, available="5000", reserved="0", requested="5000"
    ) == Decimal("0.00")
