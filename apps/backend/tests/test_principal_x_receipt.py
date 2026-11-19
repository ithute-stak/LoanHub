from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from payment_engine.principal_x_ledger_reconciliation import LedgerEvent, LedgerEventKind
from payment_engine.principal_x_receipt import build_principal_x_receipt


COMPANY = uuid4()
LOAN = uuid4()
STAMP = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)


def event(event_id, kind, amount, original=None):
    return LedgerEvent(
        event_id=event_id, company_id=COMPANY, loan_id=LOAN,
        kind=kind, amount=Decimal(amount), original_collection_id=original,
    )


def receipt(events, **overrides):
    args = dict(
        receipt_reference="PX-0001", company_id=COMPANY, loan_id=LOAN,
        collection_event_id="c1", collected_at=STAMP,
        original_principal=Decimal("1000.00"), events=tuple(events),
    )
    args.update(overrides)
    return build_principal_x_receipt(**args)


def test_receipt_shows_cumulative_net_and_remaining_cap():
    result = receipt([
        event("c1", LedgerEventKind.COLLECTION, "800"),
        event("c2", LedgerEventKind.COLLECTION, "500"),
        event("r1", LedgerEventKind.REFUND, "100", "c1"),
    ])
    assert result.amount_received == Decimal("800.00")
    assert result.cumulative_net_collected == Decimal("1200.00")
    assert result.lifetime_collection_limit == Decimal("2000.00")
    assert result.lifetime_allowance_remaining == Decimal("800.00")
    assert result.settlement_confirmed is False


def test_receipt_does_not_accept_refund_as_payment():
    with pytest.raises(ValueError, match="successful collection"):
        receipt([
            event("c1", LedgerEventKind.REFUND, "50", "c2"),
            event("c2", LedgerEventKind.COLLECTION, "50"),
        ])


def test_receipt_rejects_cross_tenant_payment():
    with pytest.raises(ValueError, match="does not belong"):
        receipt([
            replace(event("c1", LedgerEventKind.COLLECTION, "50"), company_id=uuid4())
        ])


def test_receipt_rejects_over_ceiling():
    with pytest.raises(ValueError, match="ceiling"):
        receipt([event("c1", LedgerEventKind.COLLECTION, "2000.01")])


def test_receipt_rejects_duplicate_event_id():
    with pytest.raises(ValueError, match="exactly one"):
        receipt([
            event("c1", LedgerEventKind.COLLECTION, "50"),
            event("c1", LedgerEventKind.COLLECTION, "50"),
        ])


def test_receipt_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="Timezone-aware"):
        receipt(
            [event("c1", LedgerEventKind.COLLECTION, "50")],
            collected_at=STAMP.replace(tzinfo=None),
        )


def test_receipt_rejects_unverified_currency():
    with pytest.raises(ValueError, match="currency"):
        receipt([event("c1", LedgerEventKind.COLLECTION, "50")], currency="USD")


def test_receipt_can_record_explicit_settlement_confirmation():
    result = receipt(
        [event("c1", LedgerEventKind.COLLECTION, "1200")],
        settlement_confirmed=True,
    )
    assert result.settlement_confirmed is True
