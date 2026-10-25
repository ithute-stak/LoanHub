"""Phase 12: read-only CDAS sandbox authentication smoke tests.

Provider HTTP traffic is mocked: no live credentials, requests, or financial writes.
"""
from __future__ import annotations

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


def client(handler):
    return CdasClient(
        base_url="https://sandbox.invalid",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_connection_smoke_only_calls_login():
    paths = []

    async def handler(request):
        paths.append(request.url.path)
        assert request.url.path == "/api/security/login"
        return httpx.Response(200, json={"Authorization": "sandbox-token"})

    await client(handler).check_connection()
    assert paths == ["/api/security/login"]


@pytest.mark.asyncio
async def test_invalid_sandbox_credentials_are_not_reported_as_connected():
    paths = []

    async def handler(request):
        paths.append(request.url.path)
        assert request.url.path == "/api/security/login"
        return httpx.Response(401, json={"message": "Invalid credentials"})

    with pytest.raises(CdasError):
        await client(handler).check_connection()
    assert paths == ["/api/security/login"]


def test_sandbox_profile_test_is_platform_owner_only():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "routers/platform_cdas.py").read_text(encoding="utf-8")
    start = source.index('@router.post("/companies/{company_id}/profiles/{environment}/test")')
    end = source.index('@router.post("/companies/{company_id}/live-release/approve")', start)
    code = source[start:end]
    assert "Depends(require_platform_owner)" in code
    assert "await client.check_connection()" in code
    assert "profile.last_test_status = \"connected\"" in code
    assert "profile.last_test_status = \"failed\"" in code
    for forbidden in ("add_update_deduction(", "settle_deduction(", "modify_active_deduction("):
        assert forbidden not in code
