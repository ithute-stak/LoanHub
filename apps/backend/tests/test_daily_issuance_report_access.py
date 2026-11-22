"""Security regression checks for daily issuance financial reporting."""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from routers.reports import daily_issuance_expected_returns


class ForbiddenQuery:
    def query(self, *_args, **_kwargs):
        raise AssertionError("Unauthorized report must not query financial data")


@pytest.mark.parametrize("requested_branch", [None, "other"])
def test_branch_staff_cannot_query_other_branch_or_unassigned_scope(requested_branch):
    assigned = uuid4()
    context = SimpleNamespace(
        is_platform_admin=False,
        role=UserRole.BRANCH_MANAGER,
        company_id=uuid4(),
        branch_id=assigned if requested_branch == "other" else None,
    )
    with pytest.raises(HTTPException) as error:
        daily_issuance_expected_returns(
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 21),
            company_id=context.company_id,
            branch_id=uuid4() if requested_branch == "other" else None,
            db=ForbiddenQuery(),
            context=context,
        )
    assert error.value.status_code == 403


def test_invalid_date_range_rejected_before_financial_query():
    context = SimpleNamespace(
        is_platform_admin=False,
        role=UserRole.COMPANY_OWNER,
        company_id=uuid4(),
        branch_id=None,
    )
    with pytest.raises(HTTPException) as error:
        daily_issuance_expected_returns(
            period_start=date(2026, 11, 22),
            period_end=date(2026, 11, 21),
            db=ForbiddenQuery(),
            context=context,
        )
    assert error.value.status_code == 400


def test_company_owner_cannot_request_another_company_report():
    context = SimpleNamespace(
        is_platform_admin=False,
        role=UserRole.COMPANY_OWNER,
        company_id=uuid4(),
        branch_id=None,
    )
    with pytest.raises(HTTPException) as error:
        daily_issuance_expected_returns(
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 21),
            company_id=uuid4(),
            db=ForbiddenQuery(),
            context=context,
        )
    assert error.value.status_code == 403
