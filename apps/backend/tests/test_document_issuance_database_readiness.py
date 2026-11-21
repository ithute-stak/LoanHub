"""Fail-closed deployment gate for protected official PDF issuance."""
from unittest.mock import Mock
import pytest

from services.document_issuance_database_readiness import (
    document_issuance_database_readiness,
    require_document_issuance_database_ready,
)


def _db(role, rows):
    db = Mock()
    db.bind.dialect.name = "postgresql"
    db.execute.side_effect = [
        Mock(mappings=lambda: Mock(one_or_none=lambda: role)),
        Mock(mappings=lambda: Mock(all=lambda: rows)),
    ]
    return db


def _row(name, owner="migration_owner", **overrides):
    value = dict(
        table_name=name, owner_name=owner, rls_enabled=True,
        policy_count=2, can_select=True, can_insert=True,
        can_update=False, can_delete=False,
    )
    value.update(overrides)
    return value


def test_only_restricted_non_owner_runtime_role_passes():
    role = dict(role_name="loanhub_app", rolsuper=False, rolbypassrls=False)
    db = _db(role, [
        _row("document_issuances"),
        _row("document_issuance_events"),
    ])
    assert document_issuance_database_readiness(db) == (True, ())


@pytest.mark.parametrize("change,expected", [
    (dict(owner="loanhub_app"), "runtime_owns_table"),
    (dict(can_update=True), "write_privilege_too_broad"),
    (dict(can_delete=True), "write_privilege_too_broad"),
    (dict(can_insert=False), "required_privilege_missing"),
    (dict(rls_enabled=False), "rls_policies_unavailable"),
    (dict(policy_count=1), "rls_policies_unavailable"),
])
def test_reject_insecure_issuance_database(change, expected):
    owner = change.pop("owner", "migration_owner")
    role = dict(role_name="loanhub_app", rolsuper=False, rolbypassrls=False)
    db = _db(role, [_row("document_issuances", owner=owner, **change),
                    _row("document_issuance_events")])
    ready, issues = document_issuance_database_readiness(db)
    assert not ready
    assert any(expected in issue for issue in issues)


def test_missing_issuance_table_fails_closed():
    db = _db(dict(role_name="loanhub_app", rolsuper=False, rolbypassrls=False),
             [_row("document_issuances")])
    with pytest.raises(PermissionError, match="document_issuance_events:missing"):
        require_document_issuance_database_ready(db)


def test_superuser_and_rls_override_rejected():
    for key in ("rolsuper", "rolbypassrls"):
        role = dict(role_name="loanhub_app", rolsuper=False, rolbypassrls=False)
        role[key] = True
        db = _db(role, [_row("document_issuances"), _row("document_issuance_events")])
        assert document_issuance_database_readiness(db)[0] is False
