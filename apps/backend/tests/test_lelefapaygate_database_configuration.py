import pytest

from database.config.config import settings
from database.models.lelefa_paygate_configuration import LelefaPayGateConfiguration
from services.lelefa_paygate_config_service import (
    DEFAULT_BASE_URL,
    _decrypt_api_key,
    _decrypt_webhook_secret,
    _store_api_key,
    _store_webhook_secret,
    _validate_api_key,
    _validate_base_url,
    configuration_summary,
)


def test_lelefapaygate_credentials_are_encrypted_and_masked(monkeypatch):
    monkeypatch.setattr(settings, "FERNET_SECRET_KEY", "test-master-key-that-is-not-a-production-secret")
    configuration = LelefaPayGateConfiguration(
        scope="platform",
        enabled=True,
        base_url=DEFAULT_BASE_URL,
        request_signing_enabled=True,
        timeout_seconds=15,
        webhook_tolerance_seconds=300,
        collection_provider="mpesa",
        payout_provider="mpesa",
    )
    api_key = "ipb_test_1234567890abcdef"
    webhook_secret = "whsec_1234567890abcdef"

    _store_api_key(configuration, api_key)
    _store_webhook_secret(configuration, webhook_secret)

    assert api_key not in configuration.encrypted_api_key
    assert webhook_secret not in configuration.encrypted_webhook_secret
    assert _decrypt_api_key(configuration) == api_key
    assert _decrypt_webhook_secret(configuration) == webhook_secret

    summary = configuration_summary(configuration)
    assert summary["api_key_configured"] is True
    assert summary["webhook_secret_configured"] is True
    assert summary["api_key_hint"].startswith("ipb_test_")
    assert api_key not in str(summary)
    assert webhook_secret not in str(summary)


def test_lelefapaygate_api_key_environment_prefix_is_required():
    assert _validate_api_key("ipb_live_1234567890abcdef").startswith("ipb_live_")
    with pytest.raises(ValueError, match="ipb_test_ or ipb_live_"):
        _validate_api_key("ordinary-secret-value")


def test_lelefapaygate_base_url_rejects_credentials():
    assert _validate_base_url("https://payments.example.com/api/v1/") == "https://payments.example.com/api/v1"
    with pytest.raises(ValueError, match="must not contain credentials"):
        _validate_base_url("https://user:password@payments.example.com/api/v1")
