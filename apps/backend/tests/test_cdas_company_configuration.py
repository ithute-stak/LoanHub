from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from database.config.config import settings
from integrations.cdas import CdasConfigurationError
from services import cdas_config_service as service


def _row(*, username: str, password: str, enabled: bool = True, environment: str = "test"):
    return SimpleNamespace(
        environment=environment,
        is_enabled=enabled,
        configuration={
            "base_url": "https://cdas.example.test",
            "username": username,
            "timeout_seconds": 20,
        },
        encrypted_credentials=service._serialize_password(password),
        last_test_status=None,
        last_tested_at=None,
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
