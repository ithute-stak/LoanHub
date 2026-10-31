from decimal import Decimal
import pytest

from payment_engine.allocation import DueComponent, preview_allocation


def test_component_allocation_preserves_received_plus_existing_credit():
    result = preview_allocation(
        amount_received=Decimal("600"),
        existing_unapplied_credit=Decimal("100"),
        installments=[
            DueComponent("first", Decimal("500"), Decimal("200"), Decimal("50")),
            DueComponent("second", Decimal("1000"), Decimal("0")),
        ],
    )
    assert result.amount_applied == Decimal("700.00")
    assert result.unapplied_credit == Decimal("0.00")
    assert result.allocations[0].fees_paid == Decimal("50.00")
    assert result.allocations[0].ordinary_interest_paid == Decimal("200.00")
    assert result.allocations[0].principal_paid == Decimal("450.00")


def test_excess_retained_as_credit_not_as_loan_payment():
    result = preview_allocation(
        amount_received=Decimal("2000"),
        installments=[DueComponent("one", Decimal("1000"), Decimal("200"))],
    )
    assert result.amount_applied == Decimal("1200.00")
    assert result.unapplied_credit == Decimal("800.00")


def test_zero_payment_and_empty_installments():
    result = preview_allocation(amount_received=Decimal("0"), installments=[])
    assert result.amount_applied == Decimal("0.00")


def test_duplicate_installment_rejected():
    with pytest.raises(ValueError, match="unique"):
        preview_allocation(amount_received=Decimal("200"), installments=[
            DueComponent("same", Decimal("100"), Decimal("0")),
            DueComponent("same", Decimal("100"), Decimal("0")),
        ])


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity"])
def test_invalid_payment_rejected(amount):
    with pytest.raises((ValueError, ArithmeticError)):
        preview_allocation(amount_received=Decimal(amount), installments=[])
