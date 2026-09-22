from __future__ import annotations

from services.cdas_request_budget import _account_key


def test_request_budget_key_is_case_insensitive_for_same_api_user():
    assert _account_key("Lelefa.Api.User", "test") == _account_key("  lelefa.api.user  ", "TEST")


def test_request_budget_key_separates_environments():
    assert _account_key("lelefa.api.user", "test") != _account_key("lelefa.api.user", "live")


def test_request_budget_key_does_not_expose_username():
    username = "company-secret-account-name"
    key = _account_key(username, "test")
    assert len(key) == 64
    assert username not in key
