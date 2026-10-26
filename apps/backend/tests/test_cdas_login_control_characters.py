"""Malformed provider tokens cannot be cached or used as HTTP headers."""
import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["abc\\ndef", "abc\\rdef", "abc\\x00def", "abc\\x7fdef", "abc\\tdef"])
async def test_provider_control_character_token_rejected(token):
    # Convert escaped sequences into actual embedded control characters.
    token = token.encode("utf-8").decode("unicode_escape")

    async def handler(request):
        assert request.url.path == "/api/security/login"
        return httpx.Response(200, json={"Authorization": token})

    client = CdasClient(base_url="https://sandbox.invalid", username="test", password="test", transport=httpx.MockTransport(handler))
    with pytest.raises(CdasError) as exc:
        await client.check_connection()
    assert exc.value.status_code == 502
    assert client._token is None


@pytest.mark.asyncio
async def test_plain_provider_token_still_accepted():
    async def handler(request):
        return httpx.Response(200, json={"Authorization": " token-good "})

    client = CdasClient(base_url="https://sandbox.invalid", username="test", password="test", transport=httpx.MockTransport(handler))
    await client.check_connection()
    assert client._token is not None and client._token.value == "token-good"
