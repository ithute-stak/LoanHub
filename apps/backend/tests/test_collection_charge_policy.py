from decimal import Decimal

from services.lelefa_managed_collections import (
    calculate_collection_charge,
    normalize_collection_charge_policy,
)


def _policy(**overrides):
    value = {
        "enabled": True,
        "charge_type": "percentage",
        "rate_percent": 10,
        "fixed_amount": 0,
        "basis": "amount_referred",
        "minimum_days_past_due": 120,
        "cap_amount": None,
        "clause_version": "COLLECT-001",
    }
    value.update(overrides)
    return value


def test_collection_charge_defaults_are_not_authorized():
    policy = normalize_collection_charge_policy(None)
    assert policy["enabled"] is False
    assert policy["rate_percent"] == 10.0
    assert policy["requires_signed_contract"] is True


def test_percentage_charge_uses_amount_referred_after_signed_qualifying_default():
    result = calculate_collection_charge(
        _policy(),
        amount_referred=Decimal("45000.00"),
        overdue_amount=Decimal("12000.00"),
        days_past_due=140,
        contract_signed=True,
    )
    assert result["status"] == "assessable_on_external_referral"
    assert result["basis_amount"] == "45000.00"
    assert result["charge_amount"] == "4500.00"


def test_collection_charge_is_blocked_without_fully_signed_contract():
    result = calculate_collection_charge(
        _policy(),
        amount_referred=Decimal("45000.00"),
        overdue_amount=Decimal("12000.00"),
        days_past_due=140,
        contract_signed=False,
    )
    assert result["status"] == "contract_not_signed"
    assert result["charge_amount"] == "0.00"


def test_collection_charge_is_blocked_before_contractual_arrears_threshold():
    result = calculate_collection_charge(
        _policy(minimum_days_past_due=120),
        amount_referred=Decimal("45000.00"),
        overdue_amount=Decimal("12000.00"),
        days_past_due=90,
        contract_signed=True,
    )
    assert result["status"] == "minimum_arrears_not_met"
    assert result["charge_amount"] == "0.00"


def test_collection_charge_cap_is_enforced():
    result = calculate_collection_charge(
        _policy(rate_percent=10, cap_amount=Decimal("3000")),
        amount_referred=Decimal("50000"),
        overdue_amount=Decimal("50000"),
        days_past_due=150,
        contract_signed=True,
    )
    assert result["charge_amount"] == "3000.00"


def test_overdue_amount_can_be_used_as_the_contractual_basis():
    result = calculate_collection_charge(
        _policy(basis="overdue_amount"),
        amount_referred=Decimal("50000"),
        overdue_amount=Decimal("12000"),
        days_past_due=150,
        contract_signed=True,
    )
    assert result["basis_amount"] == "12000.00"
    assert result["charge_amount"] == "1200.00"
