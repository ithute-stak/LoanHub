from __future__ import annotations

import httpx
import pytest

from integrations.cdas import CdasClient, CdasConfigurationError, CdasError
from integrations.cdas_compatible import CdasCompatibleClient


@pytest.mark.asyncio
async def test_authentication_uses_documented_login_payload_and_keeps_cookie_session():
    observed = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/security/login"
        observed["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={"Authorization": "token-123"},
            headers={"Set-Cookie": "CDASSESSION=session-123; Path=/; HttpOnly"},
        )

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )
    await client.check_connection()
    assert '"Username":"test-user"' in observed["body"]
    assert '"Password":"test-password"' in observed["body"]
    assert client._token is not None and client._token.value == "token-123"
    assert client._session_cookies.get("CDASSESSION") == "session-123"


@pytest.mark.asyncio
async def test_read_only_employee_lookup_negotiates_token_header_and_caches_successful_mode():
    logins = 0
    reads = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins, reads
        if request.url.path == "/api/security/login":
            logins += 1
            return httpx.Response(
                200,
                json={"Authorization": "token-compat"},
                headers={"Set-Cookie": "CDASSESSION=session-compat; Path=/; HttpOnly"},
            )

        assert request.url.path == "/api/employee/getDetails"
        reads += 1
        assert "CDASSESSION=session-compat" in request.headers.get("cookie", "")

        if request.headers.get("Authorization") == "token-compat":
            return httpx.Response(417, json={"message": "Authorization token is missing"})
        if request.headers.get("Token") == "token-compat":
            return httpx.Response(
                200,
                json={
                    "EmployeeNo": "0019336",
                    "Name": "Tebang",
                    "Surname": "Mosunkuthu",
                },
            )
        return httpx.Response(406, json={"message": "Invalid authorization token format"})

    client = CdasCompatibleClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    first = await client.get_employee_details("0019336")
    second = await client.get_employee_details("0019336")

    assert first["EmployeeNo"] == "0019336"
    assert second["EmployeeNo"] == "0019336"
    assert logins == 1
    assert reads == 3  # first lookup negotiates; second reuses the successful Token mode


@pytest.mark.asyncio
async def test_read_only_lookup_can_negotiate_bearer_token_format():
    read_headers: list[tuple[str | None, str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-bearer"})

        assert request.url.path == "/api/employee/check-affordability"
        read_headers.append(
            (request.headers.get("Token"), request.headers.get("Authorization"))
        )
        if request.headers.get("Token") == "Bearer token-bearer":
            return httpx.Response(200, content=b"1500.50")
        return httpx.Response(406, json={"message": "Invalid authorization token format"})

    client = CdasCompatibleClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    assert str(await client.check_affordability("EMP-1")) == "1500.50"
    assert read_headers == [
        ("token-bearer", None),
        (None, "token-bearer"),
        ("Bearer token-bearer", None),
    ]


@pytest.mark.asyncio
async def test_compatibility_client_never_negotiates_or_replays_deduction_write():
    logins = 0
    writes = 0
    payload = {
        "RequestType": 1,
        "DeductionID": 0,
        "EmployeeNo": "EMP-800",
        "LoanPolicy": 1,
        "ItemCode": "LOAN",
        "DeductionAmount": 500.0,
        "TotalInstallment": 12,
        "PrincipalAmount": 6000.0,
        "EffectiveMonth": "2026-10",
        "ReferenceNo": "REF-800",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins, writes
        if request.url.path == "/api/security/login":
            logins += 1
            return httpx.Response(200, json={"Authorization": "token-write"})
        assert request.url.path == "/api/policy/add-update-deduction"
        writes += 1
        assert request.headers.get("Token") == "token-write"
        return httpx.Response(417, json={"message": "Authorization token is missing"})

    client = CdasCompatibleClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(CdasError) as raised:
        await client.add_update_deduction(payload)

    assert raised.value.status_code == 417
    assert logins == 1
    assert writes == 1


@pytest.mark.asyncio
async def test_authentication_rejects_invalid_provider_payload():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "payload"})

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CdasError) as raised:
        await client.check_connection()
    assert raised.value.status_code == 502


@pytest.mark.asyncio
async def test_authentication_requires_complete_credentials():
    client = CdasClient(base_url="https://cdas.test", username="test-user", password=None)
    with pytest.raises(CdasConfigurationError):
        await client.check_connection()
