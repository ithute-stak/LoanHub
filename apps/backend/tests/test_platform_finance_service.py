from decimal import Decimal
from types import SimpleNamespace

from database.models.enums import PaymentDirection
from services.platform_finance_service import (
    calculate_borrower_fee,
    calculate_transaction_charge,
)


def test_flat_borrower_fee():
    config = SimpleNamespace(
        fee_type="flat",
        flat_amount=Decimal("15.00"),
        percentage=Decimal("0"),
        minimum_amount=None,
        maximum_amount=None,
    )
    assert calculate_borrower_fee(config, Decimal("5000")) == Decimal("15.00")


def test_hybrid_borrower_fee_with_cap():
    config = SimpleNamespace(
        fee_type="hybrid",
        flat_amount=Decimal("5.00"),
        percentage=Decimal("1.00"),
        minimum_amount=Decimal("10.00"),
        maximum_amount=Decimal("50.00"),
    )
    assert calculate_borrower_fee(config, Decimal("10000")) == Decimal("50.00")


def test_point_zero_zero_five_percent_charge():
    agreement = SimpleNamespace(
        inbound_percentage=Decimal("0.005"),
        outbound_percentage=Decimal("0.005"),
        inbound_flat_fee=Decimal("0"),
        outbound_flat_fee=Decimal("0"),
        minimum_charge=None,
        maximum_charge=None,
    )
    percentage, flat, charge = calculate_transaction_charge(
        agreement,
        PaymentDirection.INBOUND,
        Decimal("10000"),
    )
    assert percentage == Decimal("0.005")
    assert flat == Decimal("0.00")
    assert charge == Decimal("0.50")


def test_outbound_charge_with_flat_fee():
    agreement = SimpleNamespace(
        inbound_percentage=Decimal("0"),
        outbound_percentage=Decimal("0.25"),
        inbound_flat_fee=Decimal("0"),
        outbound_flat_fee=Decimal("2.00"),
        minimum_charge=None,
        maximum_charge=None,
    )
    _, flat, charge = calculate_transaction_charge(
        agreement,
        PaymentDirection.OUTBOUND,
        Decimal("400"),
    )
    assert flat == Decimal("2.00")
    assert charge == Decimal("3.00")
