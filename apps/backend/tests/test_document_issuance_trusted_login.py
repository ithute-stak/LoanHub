"""Fail-closed dedicated issuer login identity checks."""
from unittest.mock import Mock, patch

import pytest

from services.document_issuance_trusted_login import require_trusted_issuer_database_login


def _db(login="loanhub_document_issuer", active=None, *, superuser=False,
        bypass=False, can_login=True, create_db=False, create_role=False,
        replicate=False):
    db = Mock()
    db.bind.dialect.name = "postgresql"
    identity = dict(
        login_name=login, active_role=active or login,
        is_superuser=superuser, bypasses_rls=bypass, can_login=can_login,
        can_create_db=create_db, can_create_role=create_role,
        can_replicate=replicate,
    )
    db.execute.return_value.mappings.return_value.one_or_none.return_value = identity
    return db


def test_trusted_login_requires_exact_postgresql_session_identity():
    db = _db()
    with patch.dict("os.environ", {
        "LOANHUB_ISSUANCE_TRUSTED_DB_LOGIN": "loanhub_document_issuer",
        "DB_USER": "loanhub_app",
    }):
        require_trusted_issuer_database_login(db=db)
    db.execute.assert_called_once()


@pytest.mark.parametrize("changes", [
    {"login": "loanhub_app"},
    {"active": "migration_owner"},
    {"superuser": True},
    {"bypass": True},
    {"can_login": False},
    {"create_db": True},
    {"create_role": True},
    {"replicate": True},
])
def test_mismatched_or_privileged_sql_identity_rejected(changes):
    db = _db(**changes)
    with patch.dict("os.environ", {
        "LOANHUB_ISSUANCE_TRUSTED_DB_LOGIN": "loanhub_document_issuer",
        "DB_USER": "loanhub_app",
    }):
        with pytest.raises(PermissionError, match="Untrusted"):
            require_trusted_issuer_database_login(db=db)


@pytest.mark.parametrize("configured,ordinary", [
    ("", "loanhub_app"),
    ("loanhub_app", "loanhub_app"),
    ("loanhub_document_issuer;drop", "loanhub_app"),
])
def test_missing_shared_or_invalid_configuration_fails_without_sql(configured, ordinary):
    db = _db()
    with patch.dict("os.environ", {
        "LOANHUB_ISSUANCE_TRUSTED_DB_LOGIN": configured,
        "DB_USER": ordinary,
    }):
        with pytest.raises(PermissionError, match="not configured"):
            require_trusted_issuer_database_login(db=db)
    db.execute.assert_not_called()


def test_non_postgres_database_denied():
    db = _db()
    db.bind.dialect.name = "sqlite"
    with patch.dict("os.environ", {
        "LOANHUB_ISSUANCE_TRUSTED_DB_LOGIN": "loanhub_document_issuer",
        "DB_USER": "loanhub_app",
    }):
        with pytest.raises(PermissionError, match="not configured"):
            require_trusted_issuer_database_login(db=db)
