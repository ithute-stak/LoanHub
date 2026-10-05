from __future__ import annotations

from uuid import uuid4

import pytest

from database.tenant_context import (
    _CONTEXT_INFO_KEY,
    _restore_context_after_begin,
    bind_database_tenant_context,
)


class _RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def execute(self, statement, params):
        self.calls.append(dict(params))


class _RecordingSession:
    def __init__(self, *, active: bool) -> None:
        self.info: dict = {}
        self._active = active
        self.connection_object = _RecordingConnection()

    def in_transaction(self):
        return self._active

    def connection(self):
        return self.connection_object


def _settings(connection: _RecordingConnection) -> dict[str, str]:
    return {
        item["setting_name"]: item["setting_value"]
        for item in connection.calls
    }


def test_verified_tenant_context_is_bound_to_active_transaction() -> None:
    db = _RecordingSession(active=True)
    user_id = uuid4()
    company_id = uuid4()
    branch_id = uuid4()

    bind_database_tenant_context(
        db,  # type: ignore[arg-type]
        user_id=user_id,
        company_id=company_id,
        branch_id=branch_id,
        role="loan_officer",
        actor_scope="tenant",
    )

    settings = _settings(db.connection_object)
    assert settings == {
        "loanhub.user_id": str(user_id),
        "loanhub.company_id": str(company_id),
        "loanhub.branch_id": str(branch_id),
        "loanhub.role": "loan_officer",
        "loanhub.actor_scope": "tenant",
    }
    assert db.info[_CONTEXT_INFO_KEY] == settings


def test_context_is_restored_when_a_new_transaction_begins() -> None:
    db = _RecordingSession(active=False)
    user_id = uuid4()

    bind_database_tenant_context(
        db,  # type: ignore[arg-type]
        user_id=user_id,
        company_id=None,
        branch_id=None,
        role="platform_finance",
        actor_scope="platform",
    )
    assert db.connection_object.calls == []

    _restore_context_after_begin(
        db,  # type: ignore[arg-type]
        object(),
        db.connection_object,  # type: ignore[arg-type]
    )

    settings = _settings(db.connection_object)
    assert settings["loanhub.user_id"] == str(user_id)
    assert settings["loanhub.company_id"] == ""
    assert settings["loanhub.branch_id"] == ""
    assert settings["loanhub.role"] == "platform_finance"
    assert settings["loanhub.actor_scope"] == "platform"


def test_unknown_database_actor_scope_is_rejected() -> None:
    db = _RecordingSession(active=False)

    with pytest.raises(ValueError):
        bind_database_tenant_context(
            db,  # type: ignore[arg-type]
            user_id=uuid4(),
            role="company_admin",
            actor_scope="forged",  # type: ignore[arg-type]
        )
