"""Reversal must preserve the exact original installment payment history."""
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.rollover_compensation_posting import validate_rollover_source_history


@pytest.fixture
def original():
    return {"installment_total_due": "100.00", "installment_paid_amount": "40.00", "installment_principal_due": "70.00", "installment_interest_due": "20.00", "installment_fee_due": "10.00"}


def test_accepts_unchanged_original_partial_payment(original):
    validate_rollover_source_history(
        source=SimpleNamespace(total_due=Decimal("100"), paid_amount=Decimal("40"), principal_due=Decimal("70"), interest_due=Decimal("20"), fee_due=Decimal("10")),
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
            source=SimpleNamespace(total_due=Decimal(total), paid_amount=Decimal(paid), principal_due=Decimal("70"), interest_due=Decimal("20"), fee_due=Decimal("10")),
            original=original,
        )
    assert caught.value.status_code == 409


@pytest.mark.parametrize("snapshot", [{}, {"installment_total_due": "100"}, {"installment_paid_amount": "40"}, {"installment_total_due": "invalid", "installment_paid_amount": "40"}])
def test_missing_or_invalid_history_fails_closed(snapshot):
    with pytest.raises(HTTPException) as caught:
        validate_rollover_source_history(
            source=SimpleNamespace(total_due=Decimal("100"), paid_amount=Decimal("40"), principal_due=Decimal("70"), interest_due=Decimal("20"), fee_due=Decimal("10")),
            original=snapshot,
        )
    assert caught.value.status_code == 409

@pytest.mark.parametrize("field,changed", [
    ("principal_due", "75"),
    ("interest_due", "25"),
    ("fee_due", "15"),
])
def test_component_reclassification_rejected_even_with_same_total_and_paid(original, field, changed):
    source = SimpleNamespace(total_due=Decimal("100"), paid_amount=Decimal("40"),
                             principal_due=Decimal("70"), interest_due=Decimal("20"),
                             fee_due=Decimal("10"))
    setattr(source, field, Decimal(changed))
    with pytest.raises(HTTPException) as exc:
        validate_rollover_source_history(source=source, original=original)
    assert exc.value.status_code == 409


def test_legacy_missing_component_snapshot_fails_closed(original):
    original.pop("installment_principal_due")
    source = SimpleNamespace(total_due=Decimal("100"), paid_amount=Decimal("40"),
                             principal_due=Decimal("70"), interest_due=Decimal("20"),
                             fee_due=Decimal("10"))
    with pytest.raises(HTTPException) as exc:
        validate_rollover_source_history(source=source, original=original)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "-1"])
@pytest.mark.parametrize("field", ["installment_total_due", "installment_paid_amount"])
def test_invalid_recorded_history_amount_rejected(original, value, field):
    original[field] = value
    source = SimpleNamespace(total_due=Decimal("100"), paid_amount=Decimal("40"),
                             principal_due=Decimal("70"), interest_due=Decimal("20"),
                             fee_due=Decimal("10"))
    with pytest.raises(HTTPException) as exc:
        validate_rollover_source_history(source=source, original=original)
    assert exc.value.status_code == 409
