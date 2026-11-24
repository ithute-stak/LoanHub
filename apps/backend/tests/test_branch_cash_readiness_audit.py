"""Unit tests for read-only daily cash rollout audit classification."""
from types import MappingProxyType

from scripts.audit_branch_cash_readiness import classify, AUDIT_SQL, MAX_SESSIONS


def row(**changes):
    original = {
        "branch_id": "branch-1", "ledger_id": "ledger-1",
        "counted_opening": "120.00", "linked_count": 1,
        "linked_amount": "120.00", "posted_cash_count": 0,
    }
    original.update(changes)
    return MappingProxyType(original)


def test_matching_cash_opening_is_not_flagged():
    assert classify(row()) == []


def test_legacy_cash_session_without_ledger_requires_reconciliation():
    assert classify(row(ledger_id=None, linked_count=0)) == ["MISSING_TREASURY_DAY"]


def test_session_missing_treasury_projection_is_not_silently_accepted():
    assert classify(row(linked_count=0, posted_cash_count=3)) == [
        "MISSING_SESSION_OPENING_LINK", "CASH_POSTINGS_WITHOUT_SESSION_OPENING_LINK"
    ]


def test_cash_amount_discrepancy_and_duplicate_links_are_exposed():
    assert classify(row(linked_amount="99.00")) == ["CASH_OPENING_MISMATCH"]
    assert classify(row(linked_count=2)) == ["MULTIPLE_SESSION_OPENING_LINKS"]


def test_invalid_zero_and_missing_cash_counts():
    assert classify(row(counted_opening="0.00", linked_amount="0.00")) == []
    assert classify(row(counted_opening="-1.00")) == ["INVALID_COUNTED_OPENING"]
    assert classify(row(counted_opening=None)) == ["INVALID_COUNTED_OPENING"]


def test_audit_query_is_company_scoped_bounded_and_read_only():
    statement = str(AUDIT_SQL)
    assert "s.company_id = :company_id" in statement
    assert "LIMIT :limit" in statement
    assert MAX_SESSIONS == 1000
    assert "INSERT " not in statement.upper()
    assert "UPDATE " not in statement.upper()
    assert "DELETE " not in statement.upper()
