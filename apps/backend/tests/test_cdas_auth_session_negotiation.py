from __future__ import annotations

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


@pytest.mark.asyncio
async def test_login_session_cookie_is_forwarded_to_employee_details():
    employee_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal employee_calls
        if request.url.path == "/api/security/login":
            return httpx.Response(
                200,
                json={"Authorization": "token-123"},
                headers={"Set-Cookie": "CDASSESSION=session-123; Path=/; HttpOnly"},
            )
        if request.url.path == "/api/employee/getDetails":
            employee_calls += 1
            assert request.headers.get("Authorization") == "token-123"
            assert "CDASSESSION=session-123" in request.headers.get("Cookie", "")
            return httpx.Response(
                200,
                json={"EmployeeNo": "EMP001", "Name": "Test", "Surname": "Employee"},
            )
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    result = await client.employee_details("EMP001")
    assert result["EmployeeNo"] == "EMP001"
    assert employee_calls == 1


@pytest.mark.asyncio
async def test_employee_read_negotiates_bearer_authorization_after_raw_headers_are_rejected():
    login_count = 0
    employee_headers: list[tuple[str | None, str | None]] = []
    guarded_requests = 0

    def request_guard() -> None:
        nonlocal guarded_requests
        guarded_requests += 1

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count
        if request.url.path == "/api/security/login":
            login_count += 1
            return httpx.Response(200, json={"Authorization": "token-123"})
        if request.url.path == "/api/employee/getDetails":
            employee_headers.append(
                (request.headers.get("Authorization"), request.headers.get("Token"))
            )
            if len(employee_headers) < 3:
                return httpx.Response(417, json={"Message": "Authorization token is missing"})
            assert request.headers.get("Authorization") == "Bearer token-123"
            assert request.headers.get("Token") is None
            return httpx.Response(
                200,
                json={"EmployeeNo": "EMP001", "Name": "Test", "Surname": "Employee"},
            )
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
        request_guard=request_guard,
    )

    result = await client.employee_details("EMP001")

    assert result["EmployeeNo"] == "EMP001"
    assert login_count == 1
    assert employee_headers == [
        ("token-123", None),
        (None, "token-123"),
        ("Bearer token-123", None),
    ]
    # Every real provider request, including compatibility probes, consumes the
    # same local CDAS request budget guard.
    assert guarded_requests == 4


@pytest.mark.asyncio
async def test_successful_employee_auth_mode_is_cached_for_next_read():
    employee_headers: list[tuple[str | None, str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-123"})
        if request.url.path == "/api/employee/getDetails":
            pair = (request.headers.get("Authorization"), request.headers.get("Token"))
            employee_headers.append(pair)
            if len(employee_headers) in {1, 2}:
                return httpx.Response(417, json={"Message": "Authorization token is missing"})
            assert pair == ("Bearer token-123", None)
            return httpx.Response(
                200,
                json={"EmployeeNo": "EMP001", "Name": "Test", "Surname": "Employee"},
            )
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    await client.employee_details("EMP001")
    await client.employee_details("EMP001")

    assert employee_headers == [
        ("token-123", None),
        (None, "token-123"),
        ("Bearer token-123", None),
        ("Bearer token-123", None),
    ]


@pytest.mark.asyncio
async def test_token_family_reads_negotiate_and_cache_bearer_token_mode():
    affordability_headers: list[tuple[str | None, str | None]] = []
    deduction_headers: list[tuple[str | None, str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-123"})
        if request.url.path == "/api/employee/check-affordability":
            pair = (request.headers.get("Authorization"), request.headers.get("Token"))
            affordability_headers.append(pair)
            if len(affordability_headers) < 3:
                return httpx.Response(417, json={"Message": "Authorization token is missing"})
            assert pair == (None, "Bearer token-123")
            return httpx.Response(200, json=900.0)
        if request.url.path == "/api/policy/view-all-deduction":
            pair = (request.headers.get("Authorization"), request.headers.get("Token"))
            deduction_headers.append(pair)
            assert pair == (None, "Bearer token-123")
            return httpx.Response(200, json=[])
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    assert await client.affordability("EMP001") == 900.0
    assert await client.all_deductions("EMP001") == []
    assert affordability_headers == [
        (None, "token-123"),
        ("token-123", None),
        (None, "Bearer token-123"),
    ]
    assert deduction_headers == [(None, "Bearer token-123")]


@pytest.mark.asyncio
async def test_business_404_does_not_trigger_auth_negotiation_or_relogin():
    login_count = 0
    employee_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, employee_count
        if request.url.path == "/api/security/login":
            login_count += 1
            return httpx.Response(200, json={"Authorization": "token-123"})
        if request.url.path == "/api/employee/getDetails":
            employee_count += 1
            return httpx.Response(
                404,
                json={"Message": "Employee not found. Please check Employee Number."},
            )
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(CdasError) as raised:
        await client.employee_details("REAL-NOT-IN-TEST")

    assert raised.value.status_code == 404
    assert "Employee not found" in raised.value.message
    assert login_count == 1
    assert employee_count == 1


@pytest.mark.asyncio
async def test_all_read_auth_formats_are_retried_after_one_fresh_login_then_fail_safely():
    login_count = 0
    employee_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, employee_count
        if request.url.path == "/api/security/login":
            login_count += 1
            return httpx.Response(200, json={"Authorization": "secret-token"})
        if request.url.path == "/api/employee/getDetails":
            employee_count += 1
            return httpx.Response(417, json={"Message": "Authorization token is missing"})
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(CdasError) as raised:
        await client.employee_details("EMP001")

    assert raised.value.status_code == 417
    assert "all supported read authorization formats" in raised.value.message
    assert "secret-token" not in str(raised.value)
    assert "secret-token" not in str(raised.value.details)
    assert login_count == 2
    assert employee_count == 8


@pytest.mark.asyncio
async def test_write_remains_single_raw_token_request_even_after_read_mode_negotiation():
    write_count = 0
    employee_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal write_count, employee_count
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-123"})
        if request.url.path == "/api/employee/getDetails":
            employee_count += 1
            if employee_count < 3:
                return httpx.Response(417, json={"Message": "Authorization token is missing"})
            return httpx.Response(
                200,
                json={"EmployeeNo": "EMP001", "Name": "Test", "Surname": "Employee"},
            )
        if request.url.path == "/api/policy/add-update-deduction":
            write_count += 1
            assert request.headers.get("Token") == "token-123"
            assert request.headers.get("Authorization") is None
            return httpx.Response(417, json={"Message": "Authorization token is missing"})
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    await client.employee_details("EMP001")

    with pytest.raises(CdasError) as raised:
        await client.add_update_deduction(
            {
                "RequestType": 1,
                "DeductionID": 0,
                "EmployeeNo": "EMP001",
                "LoanPolicy": 1,
                "ItemCode": "ITEM",
                "DeductionAmount": 500.0,
                "TotalInstallment": 12,
                "PrincipalAmount": 6000.0,
                "EffectiveMonth": "2026-10",
                "ReferenceNo": "REF-001",
            }
        )

    assert raised.value.status_code == 417
    assert write_count == 1


@pytest.mark.asyncio
async def test_login_token_already_prefixed_with_bearer_is_not_double_prefixed():
    employee_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal employee_count
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "Bearer token-123"})
        if request.url.path == "/api/employee/getDetails":
            employee_count += 1
            assert request.headers.get("Authorization") == "Bearer token-123"
            assert "Bearer Bearer" not in request.headers.get("Authorization", "")
            return httpx.Response(
                200,
                json={"EmployeeNo": "EMP001", "Name": "Test", "Surname": "Employee"},
            )
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    assert (await client.employee_details("EMP001"))["EmployeeNo"] == "EMP001"
    assert employee_count == 1
