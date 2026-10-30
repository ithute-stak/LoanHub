from decimal import Decimal

import pytest

from payment_engine.policy import ArrearsPolicy, ArrearsRule, preview_arrears


def test_simple_carry_forward():
    result = preview_arrears(
        scheduled_installment=Decimal("1000"),
        prior_installment_due=Decimal("1000"),
        paid_toward_prior=Decimal("600"),
        policy=ArrearsPolicy(),
    )
    assert result.next_schedule_amount == Decimal("1400.00")
    assert result.total_due == Decimal("1400.00")


def test_fixed_schedule_separate_arrears():
    result = preview_arrears(
        scheduled_installment=Decimal("1000"),
        prior_installment_due=Decimal("1000"),
        paid_toward_prior=Decimal("600"),
        policy=ArrearsPolicy(rule=ArrearsRule.FIXED_SCHEDULE),
    )
    assert result.next_schedule_amount == Decimal("1000.00")
    assert result.separately_tracked_arrears == Decimal("400.00")
    assert result.total_due == Decimal("1400.00")


def test_interest_must_be_authorized():
    with pytest.raises(ValueError, match="authorization"):
        preview_arrears(
            scheduled_installment=Decimal("1000"),
            prior_installment_due=Decimal("1000"),
            paid_toward_prior=Decimal("600"),
            policy=ArrearsPolicy(rule=ArrearsRule.CARRY_WITH_INTEREST, periodic_arrears_rate_percent=Decimal("10")),
        )


def test_authorized_simple_arrears_interest_preview():
    result = preview_arrears(
        scheduled_installment=Decimal("1000"),
        prior_installment_due=Decimal("1000"),
        paid_toward_prior=Decimal("600"),
        policy=ArrearsPolicy(
            rule=ArrearsRule.CARRY_WITH_INTEREST,
            periodic_arrears_rate_percent=Decimal("10"),
            additional_interest_authorized=True,
        ),
    )
    assert result.permitted_additional_interest == Decimal("40.00")
    assert result.total_due == Decimal("1440.00")


def test_unpaid_installment_carries_in_full_without_interest():
    result = preview_arrears(
        scheduled_installment=Decimal("1000"),
        prior_installment_due=Decimal("1000"),
        paid_toward_prior=Decimal("0"),
        policy=ArrearsPolicy(),
    )
    assert result.total_due == Decimal("2000.00")
