from decimal import Decimal

from services.lending_operations_service import calculate_cdas_affordability, make_reference, money


def test_cdas_affordability_accepts_available_capacity():
    result = calculate_cdas_affordability(
        net_salary=Decimal("10000"),
        existing_deductions=Decimal("1500"),
        proposed_deduction=Decimal("2000"),
        maximum_deduction_percent=Decimal("40"),
        minimum_take_home=Decimal("3000"),
    )
    assert result["affordable"] is True
    assert result["maximum_total_deductions"] == Decimal("4000.00")
    assert result["available_deduction_capacity"] == Decimal("2500.00")
    assert result["take_home_after"] == Decimal("6500.00")


def test_cdas_affordability_rejects_over_deduction():
    result = calculate_cdas_affordability(
        net_salary=Decimal("5000"),
        existing_deductions=Decimal("1200"),
        proposed_deduction=Decimal("1200"),
        maximum_deduction_percent=Decimal("40"),
        minimum_take_home=Decimal("3000"),
    )
    assert result["affordable"] is False
    assert len(result["reasons"]) == 2


def test_lending_operation_references_are_prefixed_and_unique():
    first = make_reference("CDAS-MND")
    second = make_reference("CDAS-MND")
    assert first.startswith("CDAS-MND-")
    assert second.startswith("CDAS-MND-")
    assert first != second
    assert money("12.345") == Decimal("12.35")
