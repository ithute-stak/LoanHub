from datetime import date
from unittest.mock import MagicMock

from services import accounting_service


def test_read_only_parity_diagnostic_never_posts(monkeypatch):
    from services import accounting_scoped_parity
    seen = {}

    def fake_report(db, **kwargs):
        seen.update(kwargs)
        return {"native_cpp_matched": True, "authoritative": False}

    monkeypatch.setattr(accounting_scoped_parity, "scoped_trial_balance_parity", fake_report)
    db = MagicMock()
    result = accounting_service._read_only_native_parity_diagnostic(
        db, scope="company:test", from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31), branch_id=None,
    )
    assert result == {"native_cpp_matched": True, "authoritative": False}
    assert seen["scope_key"] == "company:test"
    db.commit.assert_not_called()
    db.add.assert_not_called()


def test_parity_unavailable_is_advisory_only(monkeypatch):
    from services import accounting_scoped_parity

    def broken(*args, **kwargs):
        raise ValueError("native unavailable")

    monkeypatch.setattr(accounting_scoped_parity, "scoped_trial_balance_parity", broken)
    result = accounting_service._read_only_native_parity_diagnostic(
        MagicMock(), scope="company:test",
        from_date=date(2026, 1, 1), to_date=date(2026, 1, 31),
        branch_id=None,
    )
    assert result["authoritative"] is False
    assert result["native_cpp_matched"] is False
