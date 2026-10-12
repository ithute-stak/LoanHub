"""Regression tests for accounting reversal identity and exact double-entry offsets."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from services import accounting_service


def _original():
    return SimpleNamespace(
        status="posted",
        branch_id="branch-A",
        entry_number="JE-00012",
        lines=[
            SimpleNamespace(account_id="receivable", debit=Decimal("100.25"), credit=Decimal("0")),
            SimpleNamespace(account_id="cash", debit=Decimal("0"), credit=Decimal("100.25")),
        ],
    )


def test_reversal_offsets_original_exactly_and_preserves_reference(monkeypatch):
    original = _original()
    references = []
    created = []

    def lookup(db, scope, kind, identifier):
        references.append((scope, kind, identifier))
        return original if kind == "payment_transaction" else None

    monkeypatch.setattr(accounting_service, "scope_key", lambda company_id: ("company:one", None))
    monkeypatch.setattr(accounting_service, "_journal_for_reference", lookup)
    monkeypatch.setattr(accounting_service, "accounting_business_date", lambda db, company_id: date(2026, 10, 12))
    marker = object()

    def create(db, **kwargs):
        created.append(kwargs)
        return marker

    monkeypatch.setattr(accounting_service, "create_entry", create)
    result = accounting_service.reverse_reference_accounting(
        MagicMock(), company_id="one", branch_id=None,
        reference_type="payment_transaction", reference_id="pay-1",
        user_id="user-1", reason="payment returned",
    )
    assert result is marker
    assert references == [
        ("company:one", "payment_transaction", "pay-1"),
        ("company:one", "accounting_reversal", "reversal:payment_transaction:pay-1"),
    ]
    assert len(created) == 1
    assert created[0]["reference_id"] == "reversal:payment_transaction:pay-1"
    assert created[0]["branch_id"] == "branch-A"
    assert created[0]["lines"] == [
        {"account_id": "receivable", "debit": Decimal("0"), "credit": Decimal("100.25"), "description": "Reverse JE-00012"},
        {"account_id": "cash", "debit": Decimal("100.25"), "credit": Decimal("0"), "description": "Reverse JE-00012"},
    ]
    assert created[0]["status_value"] == "posted"


def test_existing_reversal_is_returned_without_second_post(monkeypatch):
    original = _original()
    existing = object()
    monkeypatch.setattr(accounting_service, "scope_key", lambda company_id: ("company:one", None))
    monkeypatch.setattr(
        accounting_service, "_journal_for_reference",
        lambda db, scope, kind, identifier: original if kind == "payment_transaction" else existing,
    )
    create = MagicMock()
    monkeypatch.setattr(accounting_service, "create_entry", create)
    result = accounting_service.reverse_reference_accounting(
        MagicMock(), company_id="one", branch_id=None,
        reference_type="payment_transaction", reference_id="pay-1",
        user_id="user-1", reason="duplicate request",
    )
    assert result is existing
    create.assert_not_called()


def test_unposted_original_cannot_be_reversed(monkeypatch):
    original = _original()
    original.status = "draft"
    monkeypatch.setattr(accounting_service, "scope_key", lambda company_id: ("company:one", None))
    monkeypatch.setattr(accounting_service, "_journal_for_reference", lambda *args: original)
    create = MagicMock()
    monkeypatch.setattr(accounting_service, "create_entry", create)
    result = accounting_service.reverse_reference_accounting(
        MagicMock(), company_id="one", branch_id=None,
        reference_type="payment_transaction", reference_id="pay-1",
        user_id="user-1", reason="invalid attempt",
    )
    assert result is None
    create.assert_not_called()
