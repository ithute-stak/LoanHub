"""Staging gate regression: direct API calls must not bypass workstation proof.

This tests the actual router dependency instead of just the token verifier.
No live customer data or Wacom device required.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers import local_signatures as local
from services import wacom_bridge_sessions as sessions


def _ctx():
    return SimpleNamespace(company_id=uuid4(), user=SimpleNamespace(id=uuid4()),
                           staff=SimpleNamespace(is_active=True))


def test_gate_is_present_on_every_local_signature_route():
    # Router-level dependency covers client lookup, operator status and upload.
    assert local.router.dependencies
    paths = {route.path for route in local.router.routes}
    assert "/local-signatures/me/status" in paths
    assert "/local-signatures/clients/lookup" in paths
    assert "/local-signatures/captures" in paths
    assert any(getattr(dep.dependency, "__name__", "") == "_require_bridge_session"
               for dep in local.router.dependencies)


@pytest.mark.parametrize("endpoint", [
    "/local-signatures/me/status",
    "/local-signatures/clients/lookup",
    "/local-signatures/captures",
])
def test_protected_routes_inherit_gate(endpoint):
    from api.v1.router import api_router
    matches = [route for route in api_router.routes if route.path == endpoint]
    assert matches, f"Route missing: {endpoint}"
    for route in matches:
        dependency_names = {d.call.__name__ for d in route.dependant.dependencies}
        assert "_require_bridge_session" in dependency_names


def test_enforcement_denies_missing_session_when_enabled(monkeypatch):
    monkeypatch.setenv("LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION", "1")
    with pytest.raises(HTTPException) as exc:
        local._require_bridge_session(x_wacom_bridge_session=None, db=object(), context=_ctx())
    assert exc.value.status_code == 403


def test_enforcement_denies_malformed_session_when_enabled(monkeypatch):
    monkeypatch.setenv("LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION", "1")
    with pytest.raises(HTTPException) as exc:
        local._require_bridge_session(x_wacom_bridge_session="wb1_fake", db=object(), context=_ctx())
    assert exc.value.status_code == 403


def test_enforcement_cannot_be_enabled_by_unexpected_value(monkeypatch):
    for value in ("true", "yes", "on", "0", ""):
        monkeypatch.setenv("LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION", value)
        assert sessions.bridge_enforcement_enabled() is False


def test_legacy_compatibility_mode_does_not_claim_to_be_secure(monkeypatch):
    monkeypatch.delenv("LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION", raising=False)
    assert sessions.bridge_enforcement_enabled() is False
    # This preserves legacy capture while staging transitions. It MUST NOT
    # be treated as a successful workstation access control test.
