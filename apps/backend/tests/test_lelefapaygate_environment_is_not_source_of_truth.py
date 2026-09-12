from database.config.config import settings
from services.lelefa_paygate_config_service import _apply_runtime_defaults


def test_legacy_lelefapaygate_environment_values_are_overridden_by_database_runtime_defaults(monkeypatch):
    monkeypatch.setattr(settings, "LELEFAPAYGATE_ENABLED", True)
    monkeypatch.setattr(settings, "LELEFAPAYGATE_API_KEY", "ipb_live_legacy_environment_secret")
    monkeypatch.setattr(settings, "LELEFAPAYGATE_WEBHOOK_SECRET", "whsec_legacy_environment_secret")

    _apply_runtime_defaults()

    assert settings.LELEFAPAYGATE_ENABLED is False
    assert settings.LELEFAPAYGATE_API_KEY is None
    assert settings.LELEFAPAYGATE_WEBHOOK_SECRET is None
