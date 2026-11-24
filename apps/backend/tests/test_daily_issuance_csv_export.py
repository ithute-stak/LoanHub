"""CSV export regressions: scope enforcement and exact financial values."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import csv
import io

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from routers import reports


class ForbiddenQuery:
    def query(self, *_args, **_kwargs):
        raise AssertionError("Unauthorized export must not read financial data")


def test_csv_export_denies_cross_branch_access():
    context = SimpleNamespace(
        is_platform_admin=False,
        role=UserRole.BRANCH_MANAGER,
        company_id=uuid4(),
        branch_id=uuid4(),
    )
    with pytest.raises(HTTPException) as error:
        reports.export_daily_issuance_csv(
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 21),
            company_id=context.company_id,
            branch_id=uuid4(),
            db=ForbiddenQuery(),
            context=context,
        )
    assert error.value.status_code == 403


def test_csv_export_preserves_decimal_amounts_and_totals(monkeypatch):
    context = SimpleNamespace(is_platform_admin=False)
    report = {
        "basis": "current_contractual_snapshot",
        "period_start": "2026-11-01",
        "period_end": "2026-11-21",
        "daily": [{
            "date": "2026-11-21",
            "loans_issued": 2,
            "principal_issued": "1500.10",
            "expected_contractual_return": "1800.35",
            "expected_return_above_principal": "300.25",
        }],
        "totals": {
            "loans_issued": 2,
            "principal_issued": "1500.10",
            "expected_contractual_return": "1800.35",
            "expected_return_above_principal": "300.25",
        },
    }
    def fake_report(**kwargs):
        assert kwargs["context"] is context
        return report
    monkeypatch.setattr(reports, "daily_issuance_expected_returns", fake_report)
    response = reports.export_daily_issuance_csv(
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 21),
        db=ForbiddenQuery(),
        context=context,
    )
    rows = list(csv.reader(io.StringIO(response.body.decode("utf-8"))))
    assert rows[-1] == ["TOTAL", "2", "1500.10", "1800.35", "300.25"]
    assert rows[-2] == ["2026-11-21", "2", "1500.10", "1800.35", "300.25"]
    assert response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
