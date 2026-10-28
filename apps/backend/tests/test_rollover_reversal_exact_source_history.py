"""Reversal must preserve the exact original installment payment history."""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.rollover_compensation_posting import validate_rollover_source_history


@pytest.fixture
def original():
    return {"installment_total_due": "100.00", "installment_paid_amount": "40.00"}


def test_accepts_unchanged_original_partial_payment(original):
    validate_rollover_source_history(
        source=SimpleNamespace(total_due=Decimal("100"), paid_amount=Decimal("40")),
        original=original,
    )


@pytest.mark.parametrize("total,paid", [
    ("110", "50"),  # Same 60 remainder; history nevertheless changed
    ("100", "50"),
    ("110", "40"),
])
def test_rejects_changed_payment_history_even_if_remainder_is_same(original, total, paid):
    with pytest.raises(HTTPException) as caught:
        validate_rollover_source_history(
            source=SimpleNamespace(total_due=Decimal(total), paid_amount=Decimal(paid)),
            original=original,
        )
    assert caught.value.status_code == 409


@pytest.mark.parametrize("snapshot", [{}, {"installment_total_due": "100"}, {"installment_paid_amount": "40"}, {"installment_total_due": "invalid", "installment_paid_amount": "40"}])
def test_missing_or_invalid_history_fails_closed(snapshot):
    with pytest.raises(HTTPException) as caught:
        validate_rollover_source_history(
            source=SimpleNamespace(total_due=Decimal("100"), paid_amount=Decimal("40")),
            original=snapshot,
        )
    assert caught.value.status_code == 409
