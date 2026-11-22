"""Financial aggregation regression checks for the daily issuance snapshot."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from database.models.enums import UserRole
from routers import reports


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def group_by(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, rows):
        self.query_result = FakeQuery(rows)

    def query(self, *_args):
        return self.query_result


def owner_context():
    return SimpleNamespace(
        is_platform_admin=False,
        role=UserRole.COMPANY_OWNER,
        company_id=uuid4(),
        branch_id=None,
    )


def test_daily_issuance_totals_preserve_cents_and_zero_rows(monkeypatch):
    monkeypatch.setattr(reports, "require_reports", lambda _context: None)
    rows = [
        SimpleNamespace(issue_date=date(2026, 11, 21), loans_issued=2,
                        principal_issued=Decimal("1500.10"),
                        expected_contractual_return=Decimal("1800.35")),
        SimpleNamespace(issue_date=date(2026, 11, 20), loans_issued=1,
                        principal_issued=Decimal("999.95"),
                        expected_contractual_return=Decimal("1200.05")),
    ]
    result = reports.daily_issuance_expected_returns(
        period_start=date(2026, 11, 20),
        period_end=date(2026, 11, 21),
        db=FakeDB(rows),
        context=owner_context(),
    )
    assert result["basis"] == "current_contractual_snapshot"
    assert result["totals"] == {
        "loans_issued": 3,
        "principal_issued": "2500.05",
        "expected_contractual_return": "3000.40",
        "expected_return_above_principal": "500.35",
    }
    assert result["daily"][0]["expected_return_above_principal"] == "300.25"
    assert result["daily"][1]["expected_return_above_principal"] == "200.10"

    empty = reports.daily_issuance_expected_returns(
        period_start=date(2026, 11, 20),
        period_end=date(2026, 11, 21),
        db=FakeDB([]),
        context=owner_context(),
    )
    assert empty["daily"] == []
    assert empty["totals"] == {
        "loans_issued": 0,
        "principal_issued": "0.00",
        "expected_contractual_return": "0.00",
        "expected_return_above_principal": "0.00",
    }
