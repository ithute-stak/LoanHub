from decimal import Decimal

import pytest

from payment_engine.principal_x_collection_ceiling import (
    evaluate_collection_ceiling,
    require_collection_within_ceiling,
)


@pytest.mark.parametrize("collected,proposed,allowed,remaining", [
    ("0", "2000", True, "2000.00"),
    ("700", "1300", True, "1300.00"),
    ("700", "1300.01", False, "1300.00"),
    ("1999.99", "0.01", True, "0.01"),
    ("2000", "0.01", False, "0.00"),
    ("2100", "1", False, "0.00"),
])
def test_lifetime_collection_preflight(collected, proposed, allowed, remaining):
    result = evaluate_collection_ceiling(
        original_principal=Decimal("1000"),
        net_collected=Decimal(collected),
        proposed_collection=Decimal(proposed),
    )
    assert result.permitted is allowed
    assert result.remaining_allowance == Decimal(remaining)


def test_reject_over_collection():
    with pytest.raises(ValueError, match="lifetime ceiling"):
        require_collection_within_ceiling(
            original_principal=Decimal("1000"),
            net_collected=Decimal("700"),
            proposed_collection=Decimal("1300.01"),
        )


@pytest.mark.parametrize("principal,collected,proposed", [
    ("0", "0", "1"), ("1000", "-1", "1"),
    ("1000", "0", "0"), ("1000", "0", "-1"),
    ("NaN", "0", "1"),
])
def test_invalid_inputs_fail_closed(principal, collected, proposed):
    with pytest.raises(ValueError):
        evaluate_collection_ceiling(
            original_principal=Decimal(principal),
            net_collected=Decimal(collected),
            proposed_collection=Decimal(proposed),
        )
