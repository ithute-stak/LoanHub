"""Exact CDAS balance collection in cents; never submit an inflated or partial schedule."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from routers.cdas_api import _exact_cdas_repayment_period


def test_three_equal_months_repay_amount_owing():
    assert _exact_cdas_repayment_period(amount_owing=Decimal("2784.00"), deduction_amount=Decimal("928.00")) == 3


def test_division_remainder_is_not_over_collected():
    with pytest.raises(HTTPException, match="exactly settle"):
        _exact_cdas_repayment_period(amount_owing=Decimal("100.00"), deduction_amount=Decimal("33.33"))


def test_cdas_provider_maximum_600_months():
    with pytest.raises(HTTPException, match="600 months"):
        _exact_cdas_repayment_period(amount_owing=Decimal("2784.00"), deduction_amount=Decimal("3.31"))


def test_zero_balance_is_not_registered():
    with pytest.raises(HTTPException, match="No outstanding"):
        _exact_cdas_repayment_period(amount_owing=Decimal("0.00"), deduction_amount=Decimal("1.00"))


def test_fractional_cents_are_not_allowed():
    with pytest.raises(HTTPException, match="rounded to cents"):
        _exact_cdas_repayment_period(amount_owing=Decimal("100.00"), deduction_amount=Decimal("3.333"))
