from decimal import Decimal

import pytest
from pydantic import ValidationError

from payment_engine.schemas import ArrearsPolicyPayload
from payment_engine.policy import ArrearsRule


def test_company_default_policy_requires_no_interest():
    policy = ArrearsPolicyPayload()
    assert policy.rule == ArrearsRule.SIMPLE_CARRY
    assert policy.additional_interest_authorized is False


def test_interest_policy_rejects_unapproved_accrual():
    with pytest.raises(ValidationError, match="authorization"):
        ArrearsPolicyPayload(rule="carry_with_interest", periodic_arrears_rate_percent=Decimal("10"))


def test_fixed_schedule_rejects_arrears_interest():
    with pytest.raises(ValidationError, match="Only"):
        ArrearsPolicyPayload(rule="fixed_schedule", periodic_arrears_rate_percent=Decimal("10"))


def test_policy_selects_approved_interest_mode():
    policy = ArrearsPolicyPayload(
        rule="carry_with_interest", additional_interest_authorized=True,
        periodic_arrears_rate_percent=Decimal("10"),
    )
    assert policy.to_selection().snapshot()["rule"] == "carry_with_interest"
