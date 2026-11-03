from dataclasses import replace
from decimal import Decimal

import pytest

from payment_engine.reversal import (
    ReversalAllocation, ReversalRequest, preview_cash_reversal,
)


def candidate(**changes):
    defaults = dict(
        payment_id="pay-one",
        payment_status="succeeded",
        payment_method="cash",
        payment_amount=Decimal("600"),
        loan_amount_paid=Decimal("800"),
        loan_total_repayable=Decimal("3000"),
        allocations=(
            ReversalAllocation("inst-1", Decimal("400"), Decimal("500")),
            ReversalAllocation("inst-2", Decimal("200"), Decimal("300")),
        ),
        is_latest_repayment=True,
        original_journal_exists=True,
        treasury_entry_exists=True,
    )
    defaults.update(changes)
    return ReversalRequest(**defaults)


def test_exact_source_allocation_reversal_preserves_remaining_other_payments():
    impact = preview_cash_reversal(candidate())
    assert impact.reversed_amount == Decimal("600.00")
    assert impact.loan_paid_after == Decimal("200.00")
    assert impact.loan_balance_after == Decimal("2800.00")
    assert impact.installment_paid_after == (
        ("inst-1", Decimal("100.00")),
        ("inst-2", Decimal("100.00")),
    )


@pytest.mark.parametrize("changes", [
    {"payment_status": "reversed"},
    {"payment_method": "mpesa"},
    {"is_latest_repayment": False},
    {"original_journal_exists": False},
    {"treasury_entry_exists": False},
    {"treasury_entry_voided": True},
    {"has_downstream_restructure": True},
])
def test_invalid_reversal_context_rejected(changes):
    with pytest.raises(ValueError):
        preview_cash_reversal(candidate(**changes))


def test_missing_or_non_reconciling_allocations_rejected():
    with pytest.raises(ValueError, match="missing"):
        preview_cash_reversal(candidate(allocations=()))
    with pytest.raises(ValueError, match="reconcile"):
        preview_cash_reversal(candidate(allocations=(
            ReversalAllocation("inst-1", Decimal("400"), Decimal("500")),
        )))


def test_duplicate_allocation_or_superseded_schedule_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        preview_cash_reversal(candidate(allocations=(
            ReversalAllocation("inst-1", Decimal("400"), Decimal("500")),
            ReversalAllocation("inst-1", Decimal("200"), Decimal("300")),
        )))
    with pytest.raises(ValueError, match="superseded"):
        preview_cash_reversal(candidate(allocations=(
            ReversalAllocation("inst-1", Decimal("400"), Decimal("500"), True),
            ReversalAllocation("inst-2", Decimal("200"), Decimal("300")),
        )))


def test_unrelated_later_payment_must_not_be_erased():
    with pytest.raises(ValueError, match="exceeds current"):
        preview_cash_reversal(candidate(allocations=(
            ReversalAllocation("inst-1", Decimal("400"), Decimal("350")),
            ReversalAllocation("inst-2", Decimal("200"), Decimal("300")),
        )))
