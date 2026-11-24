"""Native XLSX report contract and tenant isolation tests."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from openpyxl import load_workbook

from database.models.enums import UserRole
from routers import reports


class ForbiddenQuery:
    def query(self, *_args, **_kwargs):
        raise AssertionError("Unauthorized spreadsheet must not query financial data")


def test_xlsx_export_denies_cross_branch_scope():
    context = SimpleNamespace(
        is_platform_admin=False,
        role=UserRole.BRANCH_MANAGER,
        company_id=uuid4(),
        branch_id=uuid4(),
    )
    with pytest.raises(HTTPException) as error:
        reports.export_daily_issuance_xlsx(
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 21),
            company_id=context.company_id,
            branch_id=uuid4(),
            db=ForbiddenQuery(),
            context=context,
        )
    assert error.value.status_code == 403


def test_xlsx_export_preserves_numeric_amounts(monkeypatch):
    report = {
        "period_start": "2026-11-01",
        "period_end": "2026-11-21",
        "basis": "current_contractual_snapshot",
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
    monkeypatch.setattr(
        reports, "daily_issuance_expected_returns", lambda **_kwargs: report,
    )
    response = reports.export_daily_issuance_xlsx(
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 21),
        db=ForbiddenQuery(),
        context=SimpleNamespace(),
    )
    workbook = load_workbook(BytesIO(response.body), read_only=True, data_only=True)
    sheet = workbook.active
    assert sheet["B7"].value == 2
    assert Decimal(str(sheet["C7"].value)) == Decimal("1500.10")
    assert Decimal(str(sheet["D7"].value)) == Decimal("1800.35")
    assert Decimal(str(sheet["E8"].value)) == Decimal("300.25")
    assert response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
