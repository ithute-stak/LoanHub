from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from payment_engine.principal_x_ledger_reconciliation import (
    LedgerEvent, LedgerEventKind, preflight_principal_x_collection,
    reconcile_principal_x_ledger,
)


COMPANY = uuid4()
LOAN = uuid4()


def event(event_id, kind, amount, original=None):
    return LedgerEvent(
        event_id=event_id, company_id=COMPANY, loan_id=LOAN,
        kind=kind, amount=Decimal(amount), original_collection_id=original,
    )


def reconcile(events):
    return reconcile_principal_x_ledger(
        company_id=COMPANY, loan_id=LOAN, events=events,
    )


def test_multiple_collections_and_partial_refund():
    result = reconcile([
        event("c1", LedgerEventKind.COLLECTION, "500"),
        event("c2", LedgerEventKind.COLLECTION, "300"),
        event("r1", LedgerEventKind.REFUND, "100", "c1"),
    ])
    assert result.gross_collected == Decimal("800.00")
    assert result.total_reversed_or_refunded == Decimal("100.00")
    assert result.net_collected == Decimal("700.00")


def test_full_reversal_and_refund_are_not_double_counted():
    with pytest.raises(ValueError, match="exceed"):
        reconcile([
            event("c1", LedgerEventKind.COLLECTION, "500"),
            event("r1", LedgerEventKind.REVERSAL, "500", "c1"),
            event("r2", LedgerEventKind.REFUND, "1", "c1"),
        ])


@pytest.mark.parametrize("events,reason", [
    ([event("c1", LedgerEventKind.COLLECTION, "100"), event("c1", LedgerEventKind.COLLECTION, "100")], "Duplicate"),
    ([event("r1", LedgerEventKind.REFUND, "50", "missing")], "missing"),
    ([event("c1", LedgerEventKind.COLLECTION, "-1")], "positive"),
    ([event("c1", LedgerEventKind.COLLECTION, "NaN")], "finite"),
    ([event("c1", LedgerEventKind.COLLECTION, "100", "other")], "cannot reference"),
    ([event("r1", LedgerEventKind.REVERSAL, "20")], "requires"),
])
def test_bad_ledger_rejected(events, reason):
    with pytest.raises(ValueError, match=reason):
        reconcile(events)


def test_cross_company_and_loan_rejected():
    good = event("c1", LedgerEventKind.COLLECTION, "50")
    for bad in (replace(good, company_id=uuid4()), replace(good, loan_id=uuid4())):
        with pytest.raises(ValueError, match="Cross-tenant"):
            reconcile([bad])


def test_preflight_within_two_times_principal():
    events = [event("c1", LedgerEventKind.COLLECTION, "1500")]
    result = preflight_principal_x_collection(
        company_id=COMPANY, loan_id=LOAN,
        original_principal=Decimal("1000"), events=events,
        proposed_collection=Decimal("500"), proposed_event_id="c2",
    )
    assert result.net_collected == Decimal("1500.00")


def test_preflight_rejects_exceeding_two_times_principal():
    with pytest.raises(ValueError, match="ceiling"):
        preflight_principal_x_collection(
            company_id=COMPANY, loan_id=LOAN,
            original_principal=Decimal("1000"),
            events=[event("c1", LedgerEventKind.COLLECTION, "1999")],
            proposed_collection=Decimal("2"), proposed_event_id="c2",
        )


def test_preflight_rejects_duplicate_idempotency_key():
    with pytest.raises(ValueError, match="Duplicate idempotency"):
        preflight_principal_x_collection(
            company_id=COMPANY, loan_id=LOAN,
            original_principal=Decimal("1000"),
            events=[event("c1", LedgerEventKind.COLLECTION, "100")],
            proposed_collection=Decimal("100"), proposed_event_id="c1",
        )


def test_out_of_order_offsets_reconcile():
    result = reconcile([
        event("r1", LedgerEventKind.REFUND, "50", "c1"),
        event("c1", LedgerEventKind.COLLECTION, "100"),
    ])
    assert result.net_collected == Decimal("50.00")
