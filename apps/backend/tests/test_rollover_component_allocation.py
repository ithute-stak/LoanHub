"""Unit tests for preserving source receivable classification on linked rollover."""
from decimal import Decimal
import pytest
from fastapi import HTTPException
from services.final_installment_rollover_posting import split_rollover_components


def test_fee_and_interest_are_not_capitalized_as_new_principal():
    with pytest.raises(HTTPException) as error:
        split_rollover_components(principal="70.00", interest="20.00", fees="10.00", total_due="100.00", paid_amount="92.00")
    assert error.value.status_code == 409


def test_remainder_is_exactly_conserved():
    portions = split_rollover_components(
        principal="100.00", interest="0.00", fees="0.00",
        total_due="100.00", paid_amount="75.00",
    )
    assert sum(portions) == Decimal("25.00")
    assert portions == (Decimal("25.00"), Decimal("0"), Decimal("0"))


@pytest.mark.parametrize("total,paid", [("110.00", "70.00"), ("100.00", "100.00"), ("100.00", "105.00")])
def test_nonreconciling_source_rejected(total, paid):
    with pytest.raises(HTTPException) as exc:
        split_rollover_components(
            principal="70.00", interest="20.00", fees="10.00",
            total_due=total, paid_amount=paid,
        )
    assert exc.value.status_code == 409
