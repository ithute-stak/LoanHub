from decimal import Decimal
import pytest
from fastapi import HTTPException
from services.rollover_compensation_balances import prepare_rollover_compensation_balances


def test_compensation_conserves_total_receivable():
    result = prepare_rollover_compensation_balances(
        transfer_amount="50.00", parent_balance="0",
        child_balance="50.00", child_amount_paid="0",
        original_parent_balance="50.00",
    )
    assert result["parent_balance_after"] + result["child_balance_after"] == Decimal("50.00")
    assert result["net_receivable_change"] == Decimal("0")
    assert result["no_cash_movement"] is True


@pytest.mark.parametrize("changes", [
    {"parent_balance": "1"}, {"child_balance": "49"},
    {"child_amount_paid": "1"}, {"original_parent_balance": "40"},
])
def test_changed_balances_rejected(changes):
    args = dict(transfer_amount="50", parent_balance="0",
                child_balance="50", child_amount_paid="0",
                original_parent_balance="50")
    args.update(changes)
    with pytest.raises(HTTPException) as exc:
        prepare_rollover_compensation_balances(**args)
    assert exc.value.status_code == 409
