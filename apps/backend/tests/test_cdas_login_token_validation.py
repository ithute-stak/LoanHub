"""Strict CDAS login token parsing: only nonempty strings are credentials."""

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


@pytest.mark.asyncio
@pytest.mark.parametrize("authorization", [None, False, 123, ["token"], {"token": "secret"}, "   "])
async def test_login_rejects_malformed_authorization_without_caching(authorization):
    async def provider(request):
        assert request.url.path == "/api/security/login"
        return httpx.Response(200, json={"Authorization": authorization})

    client = CdasClient(
        base_url="https://sandbox.invalid",
        username="test-user",
        password="test-pass",
        transport=httpx.MockTransport(provider),
    )
    with pytest.raises(CdasError) as exc:
        await client.check_connection()
    assert exc.value.status_code == 502
    assert client._token is None


@pytest.mark.asyncio
async def test_login_accepts_valid_string_token():
    async def provider(request):
        return httpx.Response(200, json={"Authorization": "  sandbox-token  "})

    client = CdasClient(
        base_url="https://sandbox.invalid",
        username="test-user",
        password="test-pass",
        transport=httpx.MockTransport(provider),
    )
    await client.check_connection()
    assert client._token is not None
    assert client._token.value == "sandbox-token"
