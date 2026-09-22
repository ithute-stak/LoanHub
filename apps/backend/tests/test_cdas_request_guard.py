from __future__ import annotations

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


@pytest.mark.asyncio
async def test_request_guard_counts_login_and_provider_requests():
    outbound_paths: list[str] = []
    reservations: list[int] = []

    def guard() -> None:
        reservations.append(1)

    def handler(request: httpx.Request) -> httpx.Response:
        outbound_paths.append(request.url.path)
        if request.url.path == CdasClient.LOGIN_PATH:
            return httpx.Response(200, json={"Authorization": "token"})
        if request.url.path == CdasClient.EMPLOYEE_DETAILS_PATH:
            return httpx.Response(
                200,
                json={
                    "EmployeeNo": "EMP001",
                    "Name": "Test",
                    "Surname": "Employee",
                    "DOB": "1990-01-01",
                },
            )
        if request.url.path == CdasClient.AFFORDABILITY_PATH:
            return httpx.Response(200, json=500.0)
        raise AssertionError(f"unexpected path {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.example.test",
        username="user",
        password="password",
        transport=httpx.MockTransport(handler),
        request_guard=guard,
    )

    await client.employee_details("EMP001")
    await client.affordability("EMP001")

    assert outbound_paths == [
        CdasClient.LOGIN_PATH,
        CdasClient.EMPLOYEE_DETAILS_PATH,
        CdasClient.AFFORDABILITY_PATH,
    ]
    assert len(reservations) == 3


@pytest.mark.asyncio
async def test_exhausted_local_budget_prevents_network_call():
    network_calls = 0

    def guard() -> None:
        raise CdasError(429, "local CDAS budget exhausted")

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        return httpx.Response(200, json={"Authorization": "token"})

    client = CdasClient(
        base_url="https://cdas.example.test",
        username="user",
        password="password",
        transport=httpx.MockTransport(handler),
        request_guard=guard,
    )

    with pytest.raises(CdasError) as raised:
        await client.employee_details("EMP001")

    assert raised.value.status_code == 429
    assert network_calls == 0


@pytest.mark.asyncio
async def test_read_auth_retry_reserves_login_retry_and_replayed_read():
    reservations = 0
    login_count = 0
    employee_count = 0

    def guard() -> None:
        nonlocal reservations
        reservations += 1

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, employee_count
        if request.url.path == CdasClient.LOGIN_PATH:
            login_count += 1
            return httpx.Response(200, json={"Authorization": f"token-{login_count}"})
        if request.url.path == CdasClient.EMPLOYEE_DETAILS_PATH:
            employee_count += 1
            if employee_count == 1:
                return httpx.Response(401, json={"message": "expired"})
            return httpx.Response(
                200,
                json={"EmployeeNo": "EMP001", "Name": "Test", "Surname": "Employee", "DOB": "1990-01-01"},
            )
        raise AssertionError(f"unexpected path {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.example.test",
        username="user",
        password="password",
        transport=httpx.MockTransport(handler),
        request_guard=guard,
    )

    await client.employee_details("EMP001")

    # initial login + first read + forced login + replayed read
    assert reservations == 4
    assert login_count == 2
    assert employee_count == 2
