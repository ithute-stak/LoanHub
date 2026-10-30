from decimal import Decimal

import pytest
from pydantic import ValidationError

from database.schemas.legacy_cashout import LegacyHistoryPaymentCreate
from routers.legacy_cashout import _duple_morule_terms


def test_historic_receipt_optional_and_amount_positive():
    value = LegacyHistoryPaymentCreate(paid_amount=Decimal("50.25"))
    assert value.receipt_number is None
    assert value.paid_amount == Decimal("50.25")
    with pytest.raises(ValidationError):
        LegacyHistoryPaymentCreate(paid_amount=Decimal("0"))


def test_duple_morule_settlement_uses_twice_principal_ceiling():
    limit, collectible, applied, excess = _duple_morule_terms(
        Decimal("1000"), Decimal("2500"), Decimal("2000"),
    )
    assert (limit, collectible, applied, excess) == (
        Decimal("2000.00"), Decimal("2000.00"), Decimal("2000.00"), Decimal("0.00"),
    )


def test_duple_morule_overpayment_is_not_credited_to_live_loan():
    limit, collectible, applied, excess = _duple_morule_terms(
        Decimal("1000"), Decimal("2400"), Decimal("2200"),
    )
    assert limit == Decimal("2000.00")
    assert collectible == Decimal("2000.00")
    assert applied == Decimal("2000.00")
    assert excess == Decimal("200.00")


def test_original_lower_total_limits_credit_before_double_principal():
    _, collectible, applied, excess = _duple_morule_terms(
        Decimal("1000"), Decimal("1200"), Decimal("1550"),
    )
    assert (collectible, applied, excess) == (
        Decimal("1200.00"), Decimal("1200.00"), Decimal("350.00"),
    )
