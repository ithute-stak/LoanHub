from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.config.config import settings
from integrations.cdas import CdasConfigurationError
from services import cdas_config_service as service


def _row(*, username: str, password: str, enabled: bool = True, environment: str = "test"):
    base_url = (
        service.DEFAULT_TEST_BASE_URL
        if environment == "test"
        else "https://live-cdas.example.test"
    )
    return SimpleNamespace(
        environment=environment,
        is_enabled=enabled,
        configuration={
            "base_url": base_url,
            "username": username,
            "timeout_seconds": 20,
        },
        encrypted_credentials=service._serialize_password(password),
        last_test_status=None,
        last_tested_at=None,
        configured_by_user_id=None,
    )


def _db_stub():
    return SimpleNamespace(
        add=lambda _row: None,
        commit=lambda: None,
        refresh=lambda _row: None,
    )


def test_password_is_encrypted_and_summary_never_exposes_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "FERNET_SECRET_KEY", "cdas-company-config-test-key")
    encrypted = service._serialize_password("private-cdas-password")
    assert "private-cdas-password" not in encrypted
    assert service._deserialize_password(encrypted) == "private-cdas-password"

    row = SimpleNamespace(
        environment="test",
        is_enabled=True,
        configuration={
            "base_url": service.DEFAULT_TEST_BASE_URL,
            "username": "company.api.user",
            "timeout_seconds": 20,
        },
        encrypted_credentials=encrypted,
        last_test_status="connected",
        last_tested_at=None,
    )
    summary = service.configuration_summary(row)
    serialized = repr(summary)
    assert summary["password_configured"] is True
    assert "password" not in summary
    assert "private-cdas-password" not in serialized
    assert encrypted not in serialized


@pytest.mark.parametrize(
    "value",
    [
        "http://cdas.example.test",
        "https://user:password@cdas.example.test",
        "https://cdas.example.test?token=secret",
        "https://cdas.example.test#fragment",
        "not-a-url",
    ],
)
def test_cdas_base_url_rejects_unsafe_values(value: str):
    with pytest.raises(ValueError):
        service._validate_base_url(value)


def test_test_environment_is_bound_to_official_test_url():
    service._validate_environment_base_url("test", service.DEFAULT_TEST_BASE_URL)

    with pytest.raises(ValueError) as raised:
        service._validate_environment_base_url("test", "https://live-cdas.example.test")

    assert "official test url" in str(raised.value).lower()


def test_live_environment_cannot_target_known_test_url():
    service._validate_environment_base_url("live", "https://live-cdas.example.test")

    with pytest.raises(ValueError) as raised:
        service._validate_environment_base_url("live", service.DEFAULT_TEST_BASE_URL)

    assert "cannot use the cdas test url" in str(raised.value).lower()


def test_switching_environment_clears_previous_password(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "FERNET_SECRET_KEY", "cdas-environment-switch-test-key")
    company_id = uuid4()
    row = _row(username="test-user", password="test-password", environment="test")
    monkeypatch.setattr(service, "_configuration_row", lambda _db, _company_id: row)

    service.update_configuration(
        _db_stub(),
        company_id=company_id,
        configured_by_user_id=uuid4(),
        environment="live",
        enabled=False,
        base_url="https://live-cdas.example.test",
        username="live-user",
        password=None,
        clear_password=False,
        timeout_seconds=20,
    )

    assert row.environment == "live"
    assert row.encrypted_credentials is None
    assert row.is_enabled is False


def test_switching_environment_cannot_enable_with_previous_password(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "FERNET_SECRET_KEY", "cdas-environment-enable-test-key")
    company_id = uuid4()
    row = _row(username="test-user", password="test-password", environment="test")
    monkeypatch.setattr(service, "_configuration_row", lambda _db, _company_id: row)

    with pytest.raises(ValueError) as raised:
        service.update_configuration(
            _db_stub(),
            company_id=company_id,
            configured_by_user_id=uuid4(),
            environment="live",
            enabled=True,
            base_url="https://live-cdas.example.test",
            username="live-user",
            password=None,
            clear_password=False,
            timeout_seconds=20,
        )

    assert "selected environment" in str(raised.value).lower()
    assert row.environment == "test"


def test_switching_environment_accepts_explicit_new_password(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "FERNET_SECRET_KEY", "cdas-environment-new-password-key")
    company_id = uuid4()
    row = _row(username="test-user", password="test-password", environment="test")
    monkeypatch.setattr(service, "_configuration_row", lambda _db, _company_id: row)

    service.update_configuration(
        _db_stub(),
        company_id=company_id,
        configured_by_user_id=uuid4(),
        environment="live",
        enabled=True,
        base_url="https://live-cdas.example.test",
        username="live-user",
        password="live-password",
        clear_password=False,
        timeout_seconds=20,
    )

    assert row.environment == "live"
    assert row.is_enabled is True
    assert service._deserialize_password(row.encrypted_credentials) == "live-password"


def test_company_clients_are_isolated_by_tenant(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "FERNET_SECRET_KEY", "cdas-company-isolation-test-key")
    company_a = uuid4()
    company_b = uuid4()
    rows = {
        company_a: _row(username="company-a", password="password-a"),
        company_b: _row(username="company-b", password="password-b", environment="live"),
    }
    monkeypatch.setattr(service, "_configuration_row", lambda _db, company_id: rows.get(company_id))
    service._client_cache.clear()

    client_a = service.get_company_cdas_client(object(), company_a)
    client_b = service.get_company_cdas_client(object(), company_b)

    assert client_a is not client_b
    assert client_a.username == "company-a"
    assert client_a.password == "password-a"
    assert client_b.username == "company-b"
    assert client_b.password == "password-b"


def test_mismatched_saved_environment_and_url_fail_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "FERNET_SECRET_KEY", "cdas-company-mismatch-test-key")
    company_id = uuid4()
    row = _row(username="company-a", password="password-a", environment="test")
    row.configuration = {
        **row.configuration,
        "base_url": "https://live-cdas.example.test",
    }
    monkeypatch.setattr(service, "_configuration_row", lambda _db, _company_id: row)
    service._client_cache.clear()

    with pytest.raises(CdasConfigurationError) as raised:
        service.get_company_cdas_client(object(), company_id)

    assert raised.value.status_code == 503
    assert "do not match" in raised.value.message.lower()


def test_disabled_company_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "FERNET_SECRET_KEY", "cdas-company-disabled-test-key")
    company_id = uuid4()
    row = _row(username="company-a", password="password-a", enabled=False)
    monkeypatch.setattr(service, "_configuration_row", lambda _db, _company_id: row)
    service._client_cache.clear()

    with pytest.raises(CdasConfigurationError) as raised:
        service.get_company_cdas_client(object(), company_id)

    assert raised.value.status_code == 503
    assert "disabled" in raised.value.message.lower()
