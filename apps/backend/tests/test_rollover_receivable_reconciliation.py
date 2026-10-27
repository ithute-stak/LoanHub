"""Prevent double-counting a transferred receivable in lending and accounting."""
import pytest
from fastapi import HTTPException

from services.rollover_receivable_reconciliation import validate_rollover_receivable_transfer


def plan():
    return dict(
        parent_loan_id="parent-123", approved_transfer_amount="0.69",
        new_cash_disbursement="0.00", new_interest_or_fee="0.00",
        parent_balance_after_transfer="0.00",
        child_opening_receivable="0.69",
        total_receivable_before="0.69",
        total_receivable_after="0.69",
    )


def test_neutral_subledger_rollover_has_no_cash_or_control_account_change():
    result = validate_rollover_receivable_transfer(plan=plan(), parent_outstanding="0.69")
    assert result["net_receivable_change"] == "0.00"
    assert result["net_cash_change"] == "0.00"
    assert result["general_ledger_control_change"] == "0.00"
    assert [r["direction"] for r in result["subledger_postings"]] == ["transfer_out", "transfer_in"]


@pytest.mark.parametrize("change,kwargs", [
    ({"child_opening_receivable": "1.38"}, {}),
    ({"new_cash_disbursement": "0.69"}, {}),
    ({"new_interest_or_fee": "0.01"}, {}),
    ({"total_receivable_after": "1.38"}, {}),
    ({}, {"parent_outstanding": "1.38"}),
    ({}, {"child_existing_outstanding": "0.01"}),
])
def test_duplicate_or_inconsistent_debt_transfer_rejected(change, kwargs):
    candidate = plan()
    candidate.update(change)
    args = {"parent_outstanding": "0.69", **kwargs}
    with pytest.raises(HTTPException) as error:
        validate_rollover_receivable_transfer(plan=candidate, **args)
    assert error.value.status_code == 409
