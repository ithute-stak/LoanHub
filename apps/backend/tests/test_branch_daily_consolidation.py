"""Pure consolidated statement tests; no production database writes."""
from decimal import Decimal

import pytest

from services.branch_daily_consolidation import BranchDay, consolidate_branch_day


def test_combined_statement_and_internal_transfer_elimination():
    rows = [
        BranchDay("maseru", Decimal("10000"), Decimal("4000"), Decimal("3500"),
                  Decimal("500"), internal_transfers_out=Decimal("1000")),
        BranchDay("leribe", Decimal("2000"), Decimal("500"), Decimal("100"),
                  Decimal("50"), internal_transfers_in=Decimal("1000")),
    ]
    summary = consolidate_branch_day(rows)
    assert summary["branch_count"] == 2
    assert summary["expected_closing"] == Decimal("10550.00")
    assert summary["internal_transfers_in"] == summary["internal_transfers_out"]


def test_unbalanced_transfers_fail_closed():
    with pytest.raises(ValueError, match="Unbalanced"):
        consolidate_branch_day([BranchDay("a", Decimal("100"), Decimal("0"), Decimal("0"), Decimal("0"), internal_transfers_out=Decimal("50"))])


def test_duplicate_branch_cannot_double_count():
    row = BranchDay("a", Decimal("100"), Decimal("0"), Decimal("0"), Decimal("0"))
    with pytest.raises(ValueError, match="Duplicate"):
        consolidate_branch_day([row, row])


def test_empty_company_summary_is_zero():
    summary = consolidate_branch_day([])
    assert summary["branch_count"] == 0
    assert summary["expected_closing"] == Decimal("0.00")
