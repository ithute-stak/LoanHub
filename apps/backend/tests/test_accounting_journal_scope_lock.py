"""Transaction-level serialization tests for journal reference and numbering."""
from unittest.mock import MagicMock

from services import accounting_service


def test_postgres_journal_scope_lock_is_transaction_scoped():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    accounting_service._lock_journal_scope(db, "company:A")
    db.execute.assert_called_once()
    statement, bindings = db.execute.call_args.args
    assert "pg_advisory_xact_lock" in str(statement)
    assert "hashtextextended" in str(statement)
    assert bindings == {"scope": "loanhub:journal:company:A"}
    db.commit.assert_not_called()


def test_non_postgres_does_not_execute_postgres_lock():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "sqlite"
    accounting_service._lock_journal_scope(db, "company:A")
    db.execute.assert_not_called()


def test_different_scopes_use_different_lock_inputs():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    accounting_service._lock_journal_scope(db, "company:A")
    accounting_service._lock_journal_scope(db, "company:B")
    assert db.execute.call_args_list[0].args[1] != db.execute.call_args_list[1].args[1]
