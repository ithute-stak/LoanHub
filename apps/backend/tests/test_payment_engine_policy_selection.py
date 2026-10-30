from decimal import Decimal

import pytest

from payment_engine.configuration import (
    PolicySelection, read_loan_policy_snapshot, resolve_new_loan_policy,
)
from payment_engine.policy import ArrearsRule


def test_company_default_and_product_override():
    company = PolicySelection(rule=ArrearsRule.SIMPLE_CARRY)
    product = PolicySelection(rule=ArrearsRule.FIXED_SCHEDULE, version=2)
    assert resolve_new_loan_policy(company_default=company, product_override=product) == product
    assert resolve_new_loan_policy(company_default=company, product_override=None) == company
    assert resolve_new_loan_policy(company_default=None, product_override=None).rule == ArrearsRule.SIMPLE_CARRY


def test_snapshot_is_versioned_and_does_not_change_when_company_default_changes():
    selected = PolicySelection(rule=ArrearsRule.FIXED_SCHEDULE)
    stored = selected.snapshot()
    new_default = PolicySelection(rule=ArrearsRule.SIMPLE_CARRY)
    assert read_loan_policy_snapshot(stored) == selected
    assert read_loan_policy_snapshot(stored) != new_default


def test_interest_bearing_policy_requires_authorization():
    with pytest.raises(ValueError, match="authorization"):
        PolicySelection(rule=ArrearsRule.CARRY_WITH_INTEREST, periodic_arrears_rate_percent=Decimal("10"))
    approved = PolicySelection(rule=ArrearsRule.CARRY_WITH_INTEREST, periodic_arrears_rate_percent=Decimal("10"), additional_interest_authorized=True)
    assert read_loan_policy_snapshot(approved.snapshot()) == approved


def test_no_interest_on_fixed_or_simple_carry():
    with pytest.raises(ValueError, match="Only"):
        PolicySelection(rule=ArrearsRule.SIMPLE_CARRY, periodic_arrears_rate_percent=Decimal("5"))
    with pytest.raises(ValueError, match="Only"):
        PolicySelection(rule=ArrearsRule.FIXED_SCHEDULE, additional_interest_authorized=True)
