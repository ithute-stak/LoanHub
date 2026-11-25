"""Focused offline tests; no database and no live posting."""
from decimal import Decimal

from payment_engine.principal_x_refund_reversal_preview import (
    PaymentEvidence, preview_reconciliation,
)


def row(pid, amount, direction="collection", status="completed", original=None, verified=True):
    return PaymentEvidence(pid, Decimal(amount), status, direction,
                           original_payment_id=original, verified=verified)


def test_partial_refund_is_not_a_second_collection():
    result = preview_reconciliation([
        row("p1", "1000.00"), row("r1", "250.00", "refund", original="p1"),
    ])
    assert result.gross_collected == Decimal("1000.00")
    assert result.net_collected == Decimal("750.00")
    assert result.complete is False


def test_full_refund():
    result = preview_reconciliation([
        row("p1", "1000.00"), row("r1", "1000.00", "refund", original="p1"),
    ])
    assert result.net_collected == Decimal("0.00")


def test_duplicate_id_fails_closed():
    result = preview_reconciliation([row("p1", "500"), row("p1", "500")])
    assert result.net_collected is None
    assert result.unresolved


def test_unlinked_refund_fails_closed():
    result = preview_reconciliation([row("r1", "100", "refund", original="missing")])
    assert result.net_collected is None


def test_over_refund_fails_closed():
    result = preview_reconciliation([
        row("p1", "100"), row("r1", "101", "refund", original="p1"),
    ])
    assert result.net_collected is None


def test_unverified_or_pending_fails_closed():
    result = preview_reconciliation([
        row("p1", "100", verified=False), row("p2", "100", status="pending"),
    ])
    assert result.net_collected is None


def test_unknown_reversal_does_not_disappear():
    result = preview_reconciliation([
        row("p1", "100"), row("rev1", "100", "reversal"),
    ])
    assert result.net_collected is None


def test_invalid_money_fails_closed():
    result = preview_reconciliation([row("p1", "NaN")])
    assert result.net_collected is None


def test_verified_reversal_debits_original_collection_once():
    result = preview_reconciliation([
        row("p1", "1000.00"),
        row("rv1", "300.00", "reversal", original="p1"),
    ])
    assert result.gross_collected == Decimal("1000.00")
    assert result.verified_refunds == Decimal("0.00")
    assert result.verified_reversals == Decimal("300.00")
    assert result.net_collected == Decimal("700.00")
    assert result.complete is False


def test_verified_refund_and_reversal_share_one_original_limit():
    result = preview_reconciliation([
        row("p1", "1000.00"),
        row("r1", "250.00", "refund", original="p1"),
        row("rv1", "350.00", "reversal", original="p1"),
    ])
    assert result.verified_refunds == Decimal("250.00")
    assert result.verified_reversals == Decimal("350.00")
    assert result.net_collected == Decimal("400.00")
    assert result.complete is False


def test_combined_refund_and_reversal_cannot_exceed_original_collection():
    result = preview_reconciliation([
        row("p1", "100.00"),
        row("r1", "60.00", "refund", original="p1"),
        row("rv1", "40.01", "reversal", original="p1"),
    ])
    assert result.net_collected is None
    assert "p1:deductions_exceed_collection" in result.unresolved
    assert result.complete is False


def test_reversal_without_original_collection_fails_closed():
    result = preview_reconciliation([
        row("p1", "100.00"),
        row("rv1", "20.00", "reversal", original="unknown"),
    ])
    assert result.net_collected is None
    assert "unknown:reversal_without_verified_collection" in result.unresolved


def test_unverified_reversal_does_not_reduce_verified_collection():
    result = preview_reconciliation([
        row("p1", "100.00"),
        row("rv1", "20.00", "reversal", original="p1", verified=False),
    ])
    assert result.net_collected is None
    assert result.verified_reversals == Decimal("0.00")
    assert "rv1:unverified" in result.unresolved


def test_duplicate_reversal_id_fails_closed():
    rev = row("rv1", "25.00", "reversal", original="p1")
    result = preview_reconciliation([row("p1", "100.00"), rev, rev])
    assert result.net_collected is None
    assert "missing_or_duplicate_payment_id" in result.unresolved


def test_reversal_without_verified_original_reference_fails_closed():
    result = preview_reconciliation([
        row("p1", "100.00"), row("rv1", "25.00", "reversal"),
    ])
    assert result.net_collected is None
    assert "rv1:missing_original_payment" in result.unresolved
