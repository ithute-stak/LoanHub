"""Unit tests for read-only daily cash rollout audit classification."""
from datetime import date
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


def test_stale_open_cash_session_blocks_activation_even_with_matching_opening():
    old = row(session_status="open", business_date="2026-10-21")
    assert classify(old, as_of=date(2026, 11, 25)) == ["STALE_OPEN_CASH_SESSION"]
    closed = row(session_status="closed", business_date="2026-10-21")
    assert classify(closed, as_of=date(2026, 11, 25)) == []
    same_day = row(session_status="open", business_date="2026-11-25")
    assert classify(same_day, as_of=date(2026, 11, 25)) == []
    future = row(session_status="open", business_date="2026-12-01")
    assert classify(future, as_of=date(2026, 11, 25)) == ["FUTURE_OPEN_CASH_SESSION"]
    invalid = row(session_status="open", business_date="not-a-date")
    assert classify(invalid, as_of=date(2026, 11, 25)) == ["INVALID_SESSION_BUSINESS_DATE"]


def test_posted_cash_journal_and_treasury_difference_blocks_activation():
    values = row(
        posted_journal_cash_net="2320.00",
        treasury_cash_net="2300.00",
        posted_journal_cash_count=1,
        posted_cash_count=1,
    )
    assert classify(values) == ["CASH_JOURNAL_TREASURY_MISMATCH"]
    matched = row(
        posted_journal_cash_net="2320.00",
        treasury_cash_net="2320.00",
        posted_journal_cash_count=1,
        posted_cash_count=1,
    )
    assert classify(matched) == []


def test_cash_reconciliation_audit_compares_posted_journals_with_treasury():
    statement = str(AUDIT_SQL)
    assert "journal_entries je" in statement
    assert "journal_lines jl" in statement
    assert "accounting_accounts aa" in statement
    assert "je.posted_at >=" in statement
    assert "posted_journal_cash_net" in statement
    assert "treasury_cash_net" in statement


def test_narrow_date_window_cannot_hide_company_wide_stale_cash_session(monkeypatch):
    from contextlib import nullcontext
    from datetime import date
    from uuid import uuid4
    from scripts import audit_branch_cash_readiness as audit_module

    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

        def mappings(self):
            return self

        def all(self):
            return self.value

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def begin(self):
            return nullcontext()

        def execute(self, sql, params=None):
            statement = str(sql)
            if "SET TRANSACTION READ ONLY" in statement:
                return FakeResult(None)
            if "data->>'business_date' NOT BETWEEN :from_date AND :to_date" in statement:
                assert params["company_id"] == str(company_id)
                assert "from_date" in params and "to_date" in params
                return FakeResult(0)
            if "SELECT count(*) FROM company_operating_records" in statement:
                assert params["company_id"] == str(company_id)
                assert "as_of" in params
                return FakeResult(1)
            assert "LIMIT :limit" in statement
            return FakeResult([{
                **dict(row()), "branch_id": "one", "business_date": "2026-11-25",
                "session_status": "closed",
            }])

    class FakeEngine:
        def connect(self):
            return FakeConnection()

        def dispose(self):
            pass

    monkeypatch.setattr(audit_module, "create_engine", lambda *_args, **_kwargs: FakeEngine())
    company_id = uuid4()
    result = audit_module.audit(company_id, date(2026, 11, 25), date(2026, 11, 25), "dummy")
    assert result["sessions_checked"] == 1
    assert result["issue_counts"] == {}
    assert result["company_wide_stale_open_sessions"] == 1
    assert result["company_wide_sessions_outside_range"] == 0
    assert result["ready"] is False


def test_stale_session_scope_query_is_company_wide_and_read_only():
    from scripts.audit_branch_cash_readiness import STALE_SESSIONS_SQL
    statement = str(STALE_SESSIONS_SQL)
    assert "company_id = :company_id" in statement
    assert "status = 'open'" in statement
    assert "data->>'business_date' <> :as_of" in statement
    # Any non-today open date (older, future, malformed, or blank) blocks activation.
    assert "data->>'business_date' IS NULL" in statement
    assert "BETWEEN :from_date AND :to_date" not in statement
    assert "UPDATE " not in statement.upper()
    assert "DELETE " not in statement.upper()


def test_partial_history_cannot_report_company_ready(monkeypatch):
    from contextlib import nullcontext
    from uuid import uuid4
    from scripts import audit_branch_cash_readiness as audit_module

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

        def mappings(self):
            return self

        def all(self):
            return self.value

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def begin(self):
            return nullcontext()

        def execute(self, sql, params=None):
            statement = str(sql)
            if "SET TRANSACTION READ ONLY" in statement:
                return Result(None)
            if "data->>'business_date' NOT BETWEEN :from_date AND :to_date" in statement:
                return Result(1)  # older closed session is outside selected window
            if "SELECT count(*) FROM company_operating_records" in statement:
                return Result(0)  # no stale open sessions
            return Result([{**dict(row()), "business_date": "2026-11-25",
                            "session_status": "closed"}])

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            pass

    monkeypatch.setattr(audit_module, "create_engine", lambda *_args, **_kwargs: Engine())
    report = audit_module.audit(uuid4(), date(2026, 11, 25), date(2026, 11, 25), "dummy")
    assert report["sessions_checked"] == 1
    assert report["issue_counts"] == {}
    assert report["company_wide_stale_open_sessions"] == 0
    assert report["company_wide_sessions_outside_range"] == 1
    assert report["ready"] is False


def test_coverage_query_is_company_scoped_and_read_only():
    from scripts.audit_branch_cash_readiness import OUT_OF_RANGE_SESSIONS_SQL
    statement = str(OUT_OF_RANGE_SESSIONS_SQL)
    assert "company_id = :company_id" in statement
    assert "data->>'business_date' IS NULL" in statement
    assert "NOT BETWEEN :from_date AND :to_date" in statement
    assert "UPDATE " not in statement.upper()
    assert "DELETE " not in statement.upper()
