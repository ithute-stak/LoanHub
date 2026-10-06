from __future__ import annotations

from services.cdas_config_service import configuration_summary


def test_default_configuration_reports_platform_owned_manual_integration_phase():
    summary = configuration_summary(None)
    assert summary["environment"] == "test"
    assert summary["configured"] is False
    assert summary["enabled"] is False
    assert summary["reintegration_phase"] == "manual_documented_operations"
    assert summary["profiles"]["test"]["configured"] is False
    assert summary["profiles"]["live"]["configured"] is False


def test_company_configuration_summary_never_exposes_cdas_secrets():
    summary = configuration_summary(None)
    for forbidden in ("username", "password", "item_code", "base_url", "encrypted_credentials"):
        assert forbidden not in summary
