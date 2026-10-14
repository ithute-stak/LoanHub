"""Partial CDAS mandates are bounded and never over-collect or renew silently."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from routers.cdas_api import _partial_cdas_initial_period


def test_low_headroom_registers_partial_600_month_schedule():
    amount = Decimal("2784.00")
    deduction = Decimal("3.31")
    periods = _partial_cdas_initial_period(amount_owing=amount, deduction_amount=deduction)
    assert periods == 600
    assert periods * deduction == Decimal("1986.00")
    assert amount - periods * deduction == Decimal("798.00")


def test_cent_remainder_stays_as_balance():
    periods = _partial_cdas_initial_period(amount_owing=Decimal("100.00"), deduction_amount=Decimal("33.33"))
    assert periods == 3
    assert Decimal("33.33") * periods == Decimal("99.99")


def test_exact_schedule_can_finish():
    assert _partial_cdas_initial_period(amount_owing=Decimal("2784.00"), deduction_amount=Decimal("928.00")) == 3


def test_deduction_greater_than_balance_is_rejected():
    with pytest.raises(HTTPException, match="cannot exceed"):
        _partial_cdas_initial_period(amount_owing=Decimal("10.00"), deduction_amount=Decimal("11.00"))


def test_fraction_of_cent_is_rejected():
    with pytest.raises(HTTPException, match="cent"):
        _partial_cdas_initial_period(amount_owing=Decimal("100.00"), deduction_amount=Decimal("3.333"))


def test_zero_balance_is_rejected():
    with pytest.raises(HTTPException):
        _partial_cdas_initial_period(amount_owing=Decimal("0.00"), deduction_amount=Decimal("1.00"))
