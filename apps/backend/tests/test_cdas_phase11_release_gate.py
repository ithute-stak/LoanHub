"""Phase 11: offline CDAS Test/Live release-gate readiness checks.

All cases are local configuration tests. No credentials or CDAS network traffic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services import cdas_config_service as config


NOW = datetime(2026, 10, 25, 8, 0, tzinfo=timezone.utc)


def _profile(*, status="connected", age_hours=1, item_code="TEST-CODE"):
    return SimpleNamespace(
        environment="live",
        base_url="https://cdas.invalid",
        username="integration-test",
        item_code=item_code,
        last_test_status=status,
        last_tested_at=NOW - timedelta(hours=age_hours),
    )


def _approval(profile):
    return SimpleNamespace(configuration={
        "live_release": {
            "approved_at": NOW.isoformat(),
            "approved_by_user_id": "test-platform-operator",
            "profile_fingerprint": config._profile_release_fingerprint(profile),
        },
    })


@pytest.mark.parametrize("status,age,expected_fresh", [
    ("connected", 1, True),
    ("connected", 24, True),
    ("connected", 25, False),
    ("failed", 1, False),
    (None, 1, False),
])
def test_live_connection_must_be_recent_and_successful(monkeypatch, status, age, expected_fresh):
    monkeypatch.setattr(config, "_utcnow", lambda: NOW)
    profile = _profile(status=status, age_hours=age)
    result = config.live_release_state(_approval(profile), profile=profile)
    assert result["connection_test_fresh"] is expected_fresh
    assert result["connection_test_max_age_hours"] == 24


def test_live_release_requires_exact_approved_profile_fingerprint(monkeypatch):
    monkeypatch.setattr(config, "_utcnow", lambda: NOW)
    original = _profile()
    approved = _approval(original)
    assert config.live_release_state(approved, profile=original)["approved"] is True

    changed_endpoint = _profile()
    changed_endpoint.base_url = "https://different-cdas.invalid"
    state = config.live_release_state(approved, profile=changed_endpoint)
    assert state["approved"] is False
    assert state["profile_fingerprint_matches"] is False

    changed_item_code = _profile(item_code="DIFFERENT")
    assert config.live_release_state(approved, profile=changed_item_code)["approved"] is False


def test_no_live_release_approval_is_safe_default(monkeypatch):
    monkeypatch.setattr(config, "_utcnow", lambda: NOW)
    profile = _profile()
    state = config.live_release_state(None, profile=profile)
    assert state["approved"] is False
    assert state["connection_test_fresh"] is True


def test_selected_environment_defaults_to_test():
    assert config.selected_environment(None) == "test"
    assert config.selected_environment(SimpleNamespace(environment="unrecognized")) == "test"
    assert config.selected_environment(SimpleNamespace(environment="live")) == "live"


def test_company_configuration_summary_never_returns_credentials():
    summary = config.configuration_summary(None)
    serialized = repr(summary).lower()
    for secret in ("password", "encrypted_credentials", "session-token", "secret-key"):
        assert secret not in serialized
