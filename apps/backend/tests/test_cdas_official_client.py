from __future__ import annotations

import json

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


@pytest.mark.asyncio
async def test_employee_and_affordability_use_documented_headers_and_reuse_token():
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/security/login":
            assert json.loads(request.content) == {
                "Username": "test-user",
                "Password": "test-password",
            }
            return httpx.Response(200, json={"Authorization": "token-123"})
        if request.url.path == "/api/employee/getDetails":
            assert request.headers.get("Authorization") == "token-123"
            assert request.headers.get("Token") is None
            return httpx.Response(
                200,
                json={
                    "EmployeeNo": "EMP001",
                    "Name": "Test",
                    "Surname": "Employee",
                    "Department": "QA",
                },
            )
        if request.url.path == "/api/employee/check-affordability":
            assert request.headers.get("Token") == "token-123"
            return httpx.Response(200, json=1250.75)
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    employee = await client.employee_details("EMP001")
    affordability = await client.affordability("EMP001")

    assert employee["EmployeeNo"] == "EMP001"
    assert affordability == 1250.75
    assert [request.url.path for request in calls].count("/api/security/login") == 1


@pytest.mark.asyncio
async def test_expired_token_is_refreshed_once_and_read_request_is_retried():
    login_count = 0
    deduction_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, deduction_count
        if request.url.path == "/api/security/login":
            login_count += 1
            return httpx.Response(200, json={"Authorization": f"token-{login_count}"})
        if request.url.path == "/api/policy/view-all-deduction":
            deduction_count += 1
            if deduction_count == 1:
                assert request.headers.get("Token") == "token-1"
                return httpx.Response(401, json={"Message": "Token expired"})
            assert request.headers.get("Token") == "token-2"
            return httpx.Response(200, json=[])
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    assert await client.all_deductions("EMP001") == []
    assert login_count == 2
    assert deduction_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "path", "payload"),
    [
        (
            "add_update_deduction",
            "/api/policy/add-update-deduction",
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
            },
        ),
        (
            "modify_active_deduction",
            "/api/policy/modify-active-deduction",
            {
                "EmployeeNo": "EMP001",
                "ItemCode": "ITEM",
                "TotalInstallment": 12,
                "DeductionAmount": 500.0,
                "PrincipalAmount": 6000.0,
                "DeductionID": 123,
                "EffectiveDate": "2026-10-31",
            },
        ),
        (
            "settle_deduction",
            "/api/policy/settled-deduction",
            {
                "ItemCode": "ITEM",
                "DeductionID": 123,
                "EffectiveDate": "2026-10-31T00:00:00",
                "EmployeeNo": "EMP001",
                "SettlementReason": 2,
            },
        ),
    ],
)
async def test_state_changing_request_is_not_replayed_after_auth_error(
    method_name: str,
    path: str,
    payload: dict[str, object],
):
    login_count = 0
    write_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, write_count
        if request.url.path == "/api/security/login":
            login_count += 1
            return httpx.Response(200, json={"Authorization": "token-1"})
        if request.url.path == path:
            write_count += 1
            assert request.headers.get("Token") == "token-1"
            return httpx.Response(401, json={"Message": "Token expired"})
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    method = getattr(client, method_name)
    with pytest.raises(CdasError) as raised:
        await method(payload)

    assert raised.value.status_code == 401
    assert login_count == 1
    assert write_count == 1


@pytest.mark.asyncio
async def test_write_error_preserves_documented_cdas_status_without_leaking_secrets():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "secret-token"})
        if request.url.path == "/api/policy/add-update-deduction":
            return httpx.Response(
                499,
                json={"Message": "Deduction amount exceeds maximum available fund."},
            )
        raise AssertionError(f"Unexpected CDAS request: {request.url.path}")

    client = CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(CdasError) as raised:
        await client.add_update_deduction(
            {
                "RequestType": 1,
                "DeductionID": 0,
                "EmployeeNo": "EMP001",
                "LoanPolicy": 1,
                "ItemCode": "ITEM",
                "DeductionAmount": 5000.0,
                "TotalInstallment": 12,
                "PrincipalAmount": 60000.0,
                "EffectiveMonth": "2026-10",
                "ReferenceNo": "REF-001",
            }
        )

    assert raised.value.status_code == 499
    assert "exceeds maximum available fund" in raised.value.message
    assert "secret-token" not in str(raised.value)
