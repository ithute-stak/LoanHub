from decimal import Decimal

from routers.cdas_employee_verification import net_cdas_capacity


def test_pending_loanhub_commitments_reduce_provider_capacity():
    assert net_cdas_capacity(
        provider_affordability=Decimal("2000.00"),
        pending_commitments=Decimal("1200.00"),
    ) == Decimal("800.00")


def test_pending_commitments_cannot_make_net_capacity_negative():
    assert net_cdas_capacity(
        provider_affordability=Decimal("750.00"),
        pending_commitments=Decimal("1200.00"),
    ) == Decimal("0.00")


def test_capacity_math_is_currency_quantized():
    assert net_cdas_capacity(
        provider_affordability="1850.005",
        pending_commitments="1500.004",
    ) == Decimal("350.01")
