from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.company_client_service import (
    company_client_or_404,
    normalized_monthly_debt_installment,
)


@pytest.mark.parametrize(
    ("frequency", "installment", "expected_monthly"),
    [
        ("weekly", "100.00", "433.33"),
        ("fortnightly", "100.00", "216.67"),
        ("monthly", "100.00", "100.00"),
        ("quarterly", "100.00", "33.33"),
        ("custom", "100.00", "100.00"),
    ],
)
def test_external_debt_frequency_is_normalized_for_affordability(
    frequency: str,
    installment: str,
    expected_monthly: str,
) -> None:
    """Execute the production calculation used by borrower affordability."""
    actual = normalized_monthly_debt_installment(Decimal(installment), frequency)
    assert actual == Decimal(expected_monthly)


def test_external_debt_unknown_frequency_uses_safe_monthly_fallback() -> None:
    actual = normalized_monthly_debt_installment(Decimal("750.00"), "unexpected")
    assert actual == Decimal("750.00")


class _RecordingQuery:
    def __init__(self) -> None:
        self.criteria = []

    def options(self, *args):
        return self

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self

    def first(self):
        return None


class _RecordingSession:
    def __init__(self) -> None:
        self.query_object = _RecordingQuery()

    def query(self, *args):
        return self.query_object


def test_company_client_lookup_requires_both_resource_and_tenant_ids() -> None:
    """A client ID alone must never be enough to cross a company boundary."""
    db = _RecordingSession()
    account_id = uuid4()
    company_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        company_client_or_404(
            db,  # type: ignore[arg-type]
            account_id=account_id,
            company_id=company_id,
        )

    assert exc_info.value.status_code == 404

    criteria = db.query_object.criteria
    compared_columns = {
        getattr(getattr(expression, "left", None), "key", None)
        for expression in criteria
    }
    compared_values = {
        getattr(getattr(expression, "right", None), "value", None)
        for expression in criteria
    }

    assert {"id", "company_id"}.issubset(compared_columns)
    assert account_id in compared_values
    assert company_id in compared_values
