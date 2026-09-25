from __future__ import annotations

import json

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


@pytest.mark.asyncio
async def test_employee_lookup_uses_documented_path_header_body_and_fields() -> None:
    observed: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-123"})

        assert request.url.path == "/api/employee/getDetails"
        observed["authorization"] = request.headers.get("Authorization")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(
            200,
            json={
                "EmployeeNo": "EMP-100",
                "Name": "Mpho",
                "Surname": "Mokoena",
                "DOB": "1990-01-01",
                "Department": "Finance",
                "JoiningDate": "2018-05-01",
                "TerminationDate": None,
                "UndocumentedField": "must-not-leak",
            },
        )

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    employee = await client.get_employee_details(" EMP-100 ")

    assert observed["authorization"] == "token-123"
    assert observed["body"] == {"EmployeeNo": "EMP-100"}
    assert employee == {
        "EmployeeNo": "EMP-100",
        "Name": "Mpho",
        "Surname": "Mokoena",
        "DOB": "1990-01-01",
        "Department": "Finance",
        "JoiningDate": "2018-05-01",
        "TerminationDate": None,
    }


@pytest.mark.asyncio
async def test_employee_lookup_reauthenticates_once_when_provider_session_expires() -> None:
    logins = 0
    lookups = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins, lookups
        if request.url.path == "/api/security/login":
            logins += 1
            return httpx.Response(200, json={"Authorization": f"token-{logins}"})

        lookups += 1
        if lookups == 1:
            assert request.headers.get("Authorization") == "token-1"
            return httpx.Response(419, json={"message": "session inactive"})

        assert request.headers.get("Authorization") == "token-2"
        return httpx.Response(
            200,
            json={
                "EmployeeNo": "EMP-200",
                "Name": "Lerato",
                "Surname": "Molefe",
                "DOB": "1992-03-04",
                "Department": "Health",
                "JoiningDate": "2020-02-01",
                "TerminationDate": None,
            },
        )

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    employee = await client.get_employee_details("EMP-200")

    assert employee["EmployeeNo"] == "EMP-200"
    assert logins == 2
    assert lookups == 2


@pytest.mark.asyncio
async def test_employee_lookup_preserves_provider_not_found_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-123"})
        return httpx.Response(
            404,
            json={"message": "Employee not found. Please check Employee Number."},
        )

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(CdasError) as raised:
        await client.get_employee_details("UNKNOWN")

    assert raised.value.status_code == 404
    assert "Employee not found" in raised.value.message


@pytest.mark.asyncio
async def test_employee_lookup_requires_an_employee_number() -> None:
    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
    )

    with pytest.raises(CdasError) as raised:
        await client.get_employee_details("   ")

    assert raised.value.status_code == 422
