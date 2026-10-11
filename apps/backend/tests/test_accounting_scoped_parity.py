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
