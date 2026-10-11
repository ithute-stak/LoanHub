from unittest.mock import MagicMock

import pytest

from services.accounting_rls_readiness import accounting_rls_readiness


def test_detects_missing_policies_without_writes():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    db.execute.side_effect = [
        [
            {"name": "accounting_accounts", "enabled": True, "forced": False},
            {"name": "journal_entries", "enabled": False, "forced": False},
        ],
        [{"tablename": "accounting_accounts", "cmd": "SELECT", "roles": ["public"], "qual": "true", "with_check": None}],
    ]
    result = accounting_rls_readiness(db)
    assert result["ready"] is False
    assert "journal_entries:rls_disabled" in result["findings"]
    assert "journal_lines:table_missing" in result["findings"]
    assert any(x.startswith("accounting_accounts:policy_commands_missing:") for x in result["findings"])
    assert result["advisory_only"] is True
    db.commit.assert_not_called()
    db.add.assert_not_called()


def test_all_policies_report_structural_readiness_not_security_guarantee():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    db.execute.side_effect = [
        [{"name": name, "enabled": True, "forced": False}
         for name in ("accounting_accounts", "journal_entries", "journal_lines")],
        [{"tablename": name, "cmd": "ALL"} for name in
         ("accounting_accounts", "journal_entries", "journal_lines")],
    ]
    result = accounting_rls_readiness(db)
    assert result["ready"]
    assert "does not prove tenant isolation" in result["warning"]


def test_requires_postgres():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "sqlite"
    with pytest.raises(ValueError):
        accounting_rls_readiness(db)
