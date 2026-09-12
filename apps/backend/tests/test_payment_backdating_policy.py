from datetime import date

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from utils.payment_dates import resolve_payment_date


def test_company_owner_can_backdate_payment():
    today = date(2026, 9, 8)
    assert resolve_payment_date(UserRole.COMPANY_OWNER, date(2024, 1, 15), today=today) == date(2024, 1, 15)


def test_non_owner_cannot_backdate_payment():
    with pytest.raises(HTTPException) as error:
        resolve_payment_date(UserRole.COMPANY_ADMIN, date(2024, 1, 15), today=date(2026, 9, 8))
    assert error.value.status_code == 403
    assert "Only the Company Owner" in str(error.value.detail)


def test_all_payment_roles_can_use_today():
    today = date(2026, 9, 8)
    assert resolve_payment_date(UserRole.COMPANY_ADMIN, today, today=today) == today
    assert resolve_payment_date(UserRole.FINANCE_OFFICER, None, today=today) == today


def test_future_payment_date_is_rejected_even_for_owner():
    with pytest.raises(HTTPException) as error:
        resolve_payment_date(UserRole.COMPANY_OWNER, date(2026, 9, 9), today=date(2026, 9, 8))
    assert error.value.status_code == 422
    assert "future" in str(error.value.detail).lower()
