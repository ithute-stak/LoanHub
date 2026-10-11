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


def test_predicate_without_tenant_context_is_flagged():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    names = ("accounting_accounts", "journal_entries", "journal_lines")
    db.execute.side_effect = [
        [{"name": name, "enabled": True, "forced": False} for name in names],
        [{"tablename": name, "cmd": "ALL", "qual": "account_id > 0",
          "with_check": "account_id > 0"} for name in names],
    ]
    report = accounting_rls_readiness(db)
    assert not report["ready"]
    assert all(f"{name}:tenant_context_not_detected" in report["findings"] for name in names)


def test_tenant_context_predicate_recognized():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    names = ("accounting_accounts", "journal_entries", "journal_lines")
    clause = ("current_setting('loanhub.actor_scope', true) = 'tenant' AND "
              "company_id::text = current_setting('loanhub.company_id', true)")
    db.execute.side_effect = [
        [{"name": name, "enabled": True, "forced": False} for name in names],
        [{"tablename": name, "cmd": "ALL", "qual": clause,
          "with_check": clause} for name in names],
    ]
    report = accounting_rls_readiness(db)
    assert not any("tenant_context_not_detected" in x for x in report["findings"])
