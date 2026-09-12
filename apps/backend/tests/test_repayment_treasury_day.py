from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import TreasuryDayStatus
from services.treasury_service import ensure_current_payment_day_writable


def _query_returning(value):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = value
    db = MagicMock()
    db.query.return_value = query
    return db


def test_current_day_automatic_submission_is_reopened_for_payment(monkeypatch):
    ledger = SimpleNamespace(
        id=uuid4(),
        status=TreasuryDayStatus.SUBMITTED,
        business_date=date(2026, 7, 25),
        notes=None,
        reviewed_at=None,
        reviewed_by_user_id=None,
    )
    settings = SimpleNamespace(timezone="Africa/Maseru")
    submission = SimpleNamespace(is_automatic=True)
    db = _query_returning(submission)

    result = ensure_current_payment_day_writable(
        db,
        ledger,
        settings=settings,
        occurred_at=datetime(2026, 7, 25, 18, 0, tzinfo=timezone.utc),
    )

    assert result.status == TreasuryDayStatus.REOPENED


def test_manual_current_day_submission_stays_locked():
    ledger = SimpleNamespace(
        id=uuid4(),
        status=TreasuryDayStatus.SUBMITTED,
        business_date=date(2026, 7, 25),
        notes=None,
        reviewed_at=None,
        reviewed_by_user_id=None,
    )
    settings = SimpleNamespace(timezone="Africa/Maseru")
    submission = SimpleNamespace(is_automatic=False)
    db = _query_returning(submission)

    with pytest.raises(HTTPException) as caught:
        ensure_current_payment_day_writable(
            db,
            ledger,
            settings=settings,
            occurred_at=datetime(2026, 7, 25, 18, 0, tzinfo=timezone.utc),
        )

    assert caught.value.status_code == 409
    assert "locked after submission" in str(caught.value.detail)
