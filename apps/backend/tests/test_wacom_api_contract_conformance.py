"""Conformance tests against the real LoanHub auth, lookup and capture route schemas.

No HTTP calls, production keys, borrower details or disk writes.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest

from api.v1.router import api_router
from database.schemas.auth import AuthMembershipRead, AuthUserRead, LoginRequest, LoginResponse
from routers.local_signatures import ClientLookup, CaptureSubmission
from services.wacom_png_validation import validate_wacom_png
from scripts.wacom_real_api_smoke import synthetic_png


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wacom_real_api_smoke.py"
SPEC = importlib.util.spec_from_file_location("wacom_smoke_contract_test", SCRIPT)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_real_login_and_membership_schema_match_smoke_contract():
    fields = LoginRequest.model_fields
    assert {"phone", "password", "otp", "device_name"} <= fields.keys()
    assert {"access_token", "user"} <= LoginResponse.model_fields.keys()
    assert {"company_id", "is_active"} <= AuthMembershipRead.model_fields.keys()
    assert {"is_active", "must_change_password", "memberships"} <= AuthUserRead.model_fields.keys()


def test_live_route_definitions_match_smoke_paths_and_status_codes():
    expected = {
        ("/auth/login", "POST"): 200,
        ("/local-signatures/me/status", "GET"): 200,
        ("/local-signatures/clients/lookup", "POST"): 200,
        ("/local-signatures/captures", "POST"): 202,
        ("/local-signatures/review", "GET"): 200,
    }
    actual = {
        (route.path, method): getattr(route, "status_code", None) or 200
        for route in api_router.routes
        for method in getattr(route, "methods", ())
    }
    assert {key: actual.get(key) for key in expected} == expected
    assert "national_id" in ClientLookup.model_fields
    assert {"signer_kind", "consent_reference", "capture_png_base64", "capture_sha256"} <= CaptureSubmission.model_fields.keys()


def test_synthetic_png_accepted_by_actual_backend_validator():
    validate_wacom_png(synthetic_png())


@pytest.mark.parametrize("overrides", [
    {"is_active": False},
    {"must_change_password": True},
    {"memberships": []},
    {"memberships": [{"company_id": "not-the-synthetic-company", "is_active": True}]},
    {"memberships": [{"company_id": "the-synthetic-company", "is_active": False}]},
])
def test_smoke_login_rejects_unsafe_synthetic_membership(monkeypatch, overrides):
    monkeypatch.setenv("WACOM_TEST_ALLOWED_HOST", "wacom-isolated.example.invalid")
    api = smoke.LoanHubAPI("https://wacom-isolated.example.invalid")
    user = {
        "is_active": True,
        "must_change_password": False,
        "memberships": [{"company_id": "the-synthetic-company", "is_active": True}],
    }
    user.update(overrides)
    api.request = lambda *_args, **_kwargs: (200, {"access_token": "TESTONLY", "user": user})
    with pytest.raises(RuntimeError, match="does not belong"):
        api.login("the-synthetic-company", "synthetic-phone", "synthetic-password", "")
    assert api._token == ""


def test_smoke_login_accepts_matching_active_membership_only(monkeypatch):
    monkeypatch.setenv("WACOM_TEST_ALLOWED_HOST", "wacom-isolated.example.invalid")
    api = smoke.LoanHubAPI("https://wacom-isolated.example.invalid")
    calls = []
    def fake_request(method, path, payload):
        calls.append((method, path, payload))
        return 200, {
            "access_token": "TESTONLY",
            "user": {
                "is_active": True,
                "must_change_password": False,
                "memberships": [
                    {"company_id": "the-synthetic-company", "is_active": True}
                ],
            },
        }
    api.request = fake_request
    api.login("the-synthetic-company", "synthetic-phone", "synthetic-password", "")
    assert api._company == "the-synthetic-company"
    assert calls[0][0:2] == ("POST", "/api/v1/auth/login")
    assert calls[0][2]["otp"] is None
    api.logout()
    assert api._token == ""
    assert api._company == ""
