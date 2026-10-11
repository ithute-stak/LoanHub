from datetime import date
from decimal import Decimal
from uuid import UUID
from unittest.mock import MagicMock

import pytest

from services import accounting_scoped_parity


def test_scoped_parity_uses_ephemeral_uuid_mapping(monkeypatch):
    first = UUID("00000000-0000-0000-0000-000000000010")
    second = UUID("00000000-0000-0000-0000-000000000020")
    query = MagicMock()
    db = MagicMock()
    db.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = [
        (second, Decimal("0"), Decimal("12.50")),
        (first, Decimal("12.50"), Decimal("0")),
    ]
    received = {}

    def parity(rows):
        received["rows"] = rows
        return {"native_cpp_matched": True, "python_trial_balance": "1250|1250\\n"}

    monkeypatch.setattr(accounting_scoped_parity, "advisory_trial_balance", parity)
    report = accounting_scoped_parity.scoped_trial_balance_parity(
        db, scope_key="company:test", from_date=date(2026, 1, 1), to_date=date(2026, 1, 31)
    )
    assert received["rows"] == [
        (2, Decimal("0"), Decimal("12.50")),
        (1, Decimal("12.50"), Decimal("0")),
    ]
    assert report["account_count"] == 2
    assert report["journal_line_count"] == 2
    assert report["authoritative"] is False
    db.commit.assert_not_called()
    db.add.assert_not_called()


def test_rejects_invalid_scope_or_dates():
    with pytest.raises(ValueError):
        accounting_scoped_parity.scoped_trial_balance_parity(
            MagicMock(), scope_key="", from_date=date(2026, 2, 1), to_date=date(2026, 1, 1)
        )


def test_scope_posting_and_period_filters_are_applied(monkeypatch):
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Session
    from database.models.accounting import JournalEntry, JournalLine

    captured = {}
    class QueryCapture:
        def join(self, *args):
            return self
        def filter(self, *conditions):
            captured.setdefault("conditions", []).extend(conditions)
            return self
        def all(self):
            return []

    db = MagicMock(spec=Session)
    db.query.return_value = QueryCapture()
    monkeypatch.setattr(
        accounting_scoped_parity,
        "advisory_trial_balance",
        lambda rows: {
            "native_cpp_matched": False,
            "python_trial_balance": "0|0\\n",
        },
    )
    branch = UUID("00000000-0000-0000-0000-000000000099")
    result = accounting_scoped_parity.scoped_trial_balance_parity(
        db, scope_key="company:tenant-A",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
        branch_id=branch,
    )
    compiled = [
        str(condition.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ))
        for condition in captured["conditions"]
    ]
    filters = " AND ".join(compiled)
    assert "journal_entries.scope_key = 'company:tenant-A'" in filters
    assert "journal_entries.status = 'posted'" in filters
    assert "journal_entries.entry_date BETWEEN" in filters
    assert str(branch) in filters
    assert result["native_cpp_matched"] is False
    assert result["authoritative"] is False
    db.commit.assert_not_called()
    db.add.assert_not_called()


def test_empty_tenant_ledger_is_safe_and_non_authoritative(monkeypatch):
    db = MagicMock()
    query = db.query.return_value
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = []
    monkeypatch.setattr(
        accounting_scoped_parity, "advisory_trial_balance",
        lambda rows: {"native_cpp_matched": False, "python_trial_balance": "0|0\\n"},
    )
    report = accounting_scoped_parity.scoped_trial_balance_parity(
        db, scope_key="company:empty",
        from_date=date(2026, 1, 1), to_date=date(2026, 1, 31),
    )
    assert report["account_count"] == 0
    assert report["journal_line_count"] == 0
    assert report["authoritative"] is False
    db.commit.assert_not_called()
