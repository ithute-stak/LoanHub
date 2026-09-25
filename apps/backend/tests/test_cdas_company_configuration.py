from __future__ import annotations

import pytest

from services.cdas_config_service import (
    DEFAULT_TEST_BASE_URL,
    _validate_base_url,
    _validate_environment_base_url,
    configuration_summary,
)


def test_default_configuration_reports_documented_manual_integration_phase():
    summary = configuration_summary(None)
    assert summary["environment"] == "test"
    assert summary["base_url"] == DEFAULT_TEST_BASE_URL
    assert summary["configured"] is False
    assert summary["reintegration_phase"] == "manual_documented_operations"


def test_cdas_base_url_requires_https():
    with pytest.raises(ValueError):
        _validate_base_url("http://example.test")


def test_test_environment_is_pinned_to_official_test_host():
    with pytest.raises(ValueError):
        _validate_environment_base_url("test", "https://example.test")
