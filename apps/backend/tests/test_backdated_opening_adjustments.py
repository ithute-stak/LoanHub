from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import OpeningSourceType, PaymentMethod
from services import backdated_opening_adjustment_service as service


ROOT = Path(__file__).resolve().parents[3]
FRONTEND_LAYOUT = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "expense-management" / "layout.tsx"
FRONTEND_PAGE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "expense-management" / "backdated-opening" / "page.tsx"
FRONTEND_API = ROOT / "apps" / "frontend" / "api" / "expenseManagement.ts"
API_ROUTER = ROOT / "apps" / "backend" / "api" / "v1" / "router.py"


def _call_service(monkeypatch: pytest.MonkeyPatch, **overrides):
    monkeypatch.setattr(service, "get_or_create_settings", lambda _db, _company_id: object())
    monkeypatch.setattr(service, "local_business_date", lambda _settings: date(2026, 9, 26))
    values = {
        "db": object(),
        "company_id": uuid4(),
        "branch_id": uuid4(),
        "user_id": uuid4(),
        "business_date": date(2026, 9, 25),
        "source_type": OpeningSourceType.OPENING_ADJUSTMENT,
        "payment_method": PaymentMethod.CASH,
        "amount": Decimal("100.00"),
        "currency": "LSL",
        "description": "Historical till float",
        "correction_reason": "Opening float was omitted during initial capture",
    }
    values.update(overrides)
    return service.create_backdated_opening_adjustment(**values)  # type: ignore[arg-type]


def test_backdated_adjustment_rejects_today_or_future_date(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _call_service(monkeypatch, business_date=date(2026, 9, 26))

    assert exc_info.value.status_code == 422
    assert "before today" in str(exc_info.value.detail)


def test_backdated_adjustment_rejects_system_controlled_opening_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _call_service(monkeypatch, source_type=OpeningSourceType.PREVIOUS_CLOSING)

    assert exc_info.value.status_code == 422
    assert "system-controlled" in str(exc_info.value.detail)


def test_backdated_adjustment_requires_a_meaningful_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _call_service(monkeypatch, correction_reason="too short")

    assert exc_info.value.status_code == 422
    assert "at least 10 characters" in str(exc_info.value.detail)


def test_historical_opening_accounting_posts_balanced_closed_period_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    company_id = uuid4()
    branch_id = uuid4()
    user_id = uuid4()
    source_id = uuid4()
    debit_id = uuid4()
    credit_id = uuid4()
    captured: dict[str, object] = {}

    source = SimpleNamespace(
        id=source_id,
        company_id=company_id,
        branch_id=branch_id,
        recorded_by_user_id=user_id,
        source_type=OpeningSourceType.OPENING_ADJUSTMENT,
        amount=Decimal("250.00"),
        description="Historical cash float",
        daily_ledger=SimpleNamespace(business_date=date(2026, 9, 1)),
    )

    monkeypatch.setattr(service, "scope_key", lambda _company_id: ("company:test", None))
    monkeypatch.setattr(service, "ensure_chart", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "account_by_code",
        lambda _db, _key, code: SimpleNamespace(id=debit_id if code == "1000" else credit_id),
    )

    def capture_entry(_db, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(service, "create_entry", capture_entry)

    service._post_historical_opening_source_accounting(object(), source)  # type: ignore[arg-type]

    assert captured["allow_closed_period"] is True
    assert captured["entry_date"] == date(2026, 9, 1)
    assert captured["reference_type"] == "opening_source"
    assert captured["reference_id"] == str(source_id)
    assert captured["status_value"] == "posted"
    assert captured["lines"] == [
        {"account_id": debit_id, "debit": Decimal("250.00"), "credit": 0},
        {"account_id": credit_id, "debit": 0, "credit": Decimal("250.00")},
    ]


def test_frontend_and_api_keep_historical_correction_reachable_and_wired() -> None:
    layout = FRONTEND_LAYOUT.read_text(encoding="utf-8")
    page = FRONTEND_PAGE.read_text(encoding="utf-8")
    api = FRONTEND_API.read_text(encoding="utf-8")
    router = API_ROUTER.read_text(encoding="utf-8")

    assert 'href={HISTORICAL_PATH}' in layout
    assert '"/company/expense-management/backdated-opening"' in layout
    assert 'activeRole === "finance_officer"' in layout
    assert "createBackdatedOpeningAdjustment" in page
    assert '"/expense-management/opening-sources/backdated-adjustment"' in api
    assert "backdated_opening_adjustments.router" in router
