"""Guard financial-book summary aggregation against account-count N+1 regressions."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

from routers.accounting import _ledger_book_summary_data


def test_summary_query_count_independent_of_account_count():
    accounts = [
        SimpleNamespace(
            id=UUID(int=i + 1), code=f"A{i}", name=f"Account {i}",
            account_type="asset", normal_balance="debit",
        ) for i in range(250)
    ]
    db = MagicMock()
    db.query.return_value.join.return_value.filter.return_value.group_by.return_value.all.return_value = []
    result = _ledger_book_summary_data(
        db, key="company:budget", accounts=accounts,
        from_date=date(2026, 1, 1), to_date=date(2026, 12, 31), branch_id=None,
    )
    assert db.query.call_count == 2
    assert len(result) == 250
    assert all(row["opening_balance"] == Decimal("0.00") for row in result)
    assert all(row["closing_balance"] == Decimal("0.00") for row in result)
    assert all(row["lines"] == [] for row in result)


def test_empty_summary_skips_queries():
    db = MagicMock()
    assert _ledger_book_summary_data(
        db, key="company:budget", accounts=[],
        from_date=date(2026, 1, 1), to_date=date(2026, 12, 31), branch_id=None,
    ) == []
    db.query.assert_not_called()
