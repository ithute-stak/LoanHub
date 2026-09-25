from __future__ import annotations

import httpx
import pytest
from integrations.cdas import CdasClient, CdasConfigurationError, CdasError

@pytest.mark.asyncio
async def test_authentication_uses_documented_login_payload_and_keeps_cookie_session():
    observed = {}
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/security/login"; observed["body"] = request.read().decode()
        return httpx.Response(200, json={"Authorization": "token-123"}, headers={"Set-Cookie": "CDASSESSION=session-123; Path=/; HttpOnly"})
    client = CdasClient(base_url="https://cdas.test", username="test-user", password="test-password", transport=httpx.MockTransport(handler))
    await client.check_connection()
    assert '"Username":"test-user"' in observed["body"] and '"Password":"test-password"' in observed["body"]
    assert client._token is not None and client._token.value == "token-123"
    assert client._session_cookies.get("CDASSESSION") == "session-123"

@pytest.mark.asyncio
async def test_authentication_rejects_invalid_provider_payload():
    async def handler(_: httpx.Request) -> httpx.Response: return httpx.Response(200, json={"unexpected": "payload"})
    client = CdasClient(base_url="https://cdas.test", username="test-user", password="test-password", transport=httpx.MockTransport(handler))
    with pytest.raises(CdasError) as raised: await client.check_connection()
    assert raised.value.status_code == 502

@pytest.mark.asyncio
async def test_authentication_requires_complete_credentials():
    client = CdasClient(base_url="https://cdas.test", username="test-user", password=None)
    with pytest.raises(CdasConfigurationError): await client.check_connection()
