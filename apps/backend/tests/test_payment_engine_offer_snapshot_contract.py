from pathlib import Path

from payment_engine.configuration import PolicySelection, read_loan_policy_snapshot
from payment_engine.policy import ArrearsRule


def test_accepted_offer_loans_capture_versioned_arrears_policy():
    source = Path(__file__).resolve().parents[1] / "services" / "loan_service.py"
    text = source.read_text()
    start = text.index("def accept_offer(")
    end = text.index("def _cash_reference(", start)
    workflow = text[start:end]
    assert "selected_policy(" in workflow
    assert "company_id=offer.company_id" in workflow
    assert 'offer_breakdown["payment_engine_arrears_policy"]' in workflow
    assert "calculation_breakdown=offer_breakdown" in workflow


def test_snapshot_round_trip_stays_unchanged_when_default_changes():
    original = PolicySelection(rule=ArrearsRule.FIXED_SCHEDULE, version=2)
    stored = original.snapshot()
    future_default = PolicySelection(rule=ArrearsRule.SIMPLE_CARRY, version=3)
    assert read_loan_policy_snapshot(stored) == original
    assert read_loan_policy_snapshot(stored) != future_default
