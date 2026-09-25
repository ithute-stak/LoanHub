from __future__ import annotations

import json

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


def make_client(handler) -> CdasClient:
    return CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_affordability_uses_token_header_and_documented_contract() -> None:
    observed: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-123"})

        observed["path"] = request.url.path
        observed["token"] = request.headers.get("Token")
        observed["authorization"] = request.headers.get("Authorization")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(200, json=1875.5)

    affordability = await make_client(handler).check_affordability(" EMP-300 ")

    assert affordability == 1875.5
    assert observed == {
        "path": "/api/employee/check-affordability",
        "token": "token-123",
        "authorization": None,
        "body": {"EmployeeNo": "EMP-300"},
    }


@pytest.mark.asyncio
async def test_affordability_rejects_non_numeric_provider_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-123"})
        return httpx.Response(200, json={"Affordability": 1200})

    with pytest.raises(CdasError) as raised:
        await make_client(handler).check_affordability("EMP-300")

    assert raised.value.status_code == 502


@pytest.mark.asyncio
async def test_all_third_party_deductions_use_documented_contract() -> None:
    observed: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-abc"})

        observed["path"] = request.url.path
        observed["token"] = request.headers.get("Token")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(
            200,
            json=[
                {
                    "EmployeeNo": "EMP-400",
                    "DeductionType": "Loan",
                    "DeductionAmount": 800.0,
                    "DeductionStatus": "Active",
                }
            ],
        )

    deductions = await make_client(handler).view_all_deductions("EMP-400")

    assert observed == {
        "path": "/api/policy/view-all-deduction",
        "token": "token-abc",
        "body": {"EmployeeNo": "EMP-400"},
    }
    assert deductions[0]["DeductionAmount"] == 800.0


@pytest.mark.asyncio
async def test_own_deductions_send_status_without_transforming_provider_response() -> None:
    observed: dict[str, object] = {}
    provider_record = {
        "DeductionID": 44,
        "ItemCode": "ABC",
        "EmployeeNo": "EMP-500",
        "Name": "Test",
        "Surname": "Employee",
        "DeductionAmount": 550.0,
        "DeductionStatus": 5,
        "ReferenceNo": "REF-1",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-own"})

        observed["path"] = request.url.path
        observed["token"] = request.headers.get("Token")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(200, json=[provider_record])

    deductions = await make_client(handler).view_own_deductions("EMP-500", 5)

    assert observed == {
        "path": "/api/policy/view-deduction",
        "token": "token-own",
        "body": {"EmployeeNo": "EMP-500", "DeductionStatus": 5},
    }
    assert deductions == [provider_record]


@pytest.mark.asyncio
async def test_active_approved_lookup_uses_documented_contract() -> None:
    observed: dict[str, object] = {}
    provider_record = {
        "DeductionID": 99,
        "DeductionTypeID": 1,
        "TotalInstallment": 12,
        "ItemCode": "ABC",
        "ReferenceNo": "REF-2",
        "DeductionAmount": 700.0,
        "PrincipalAmount": 8400.0,
        "EmployeeNo": "EMP-600",
        "Name": "Test",
        "Surname": "Employee",
        "EffectiveDate": "2026-10",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-active"})

        observed["path"] = request.url.path
        observed["token"] = request.headers.get("Token")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(200, json=provider_record)

    deduction = await make_client(handler).get_active_and_approved_deduction("EMP-600")

    assert observed == {
        "path": "/api/policy/get-active-and-approved-deduction",
        "token": "token-active",
        "body": {"EmployeeNo": "EMP-600"},
    }
    assert deduction == provider_record


@pytest.mark.asyncio
async def test_policy_read_reauthentication_preserves_token_header() -> None:
    logins = 0
    requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins, requests
        if request.url.path == "/api/security/login":
            logins += 1
            return httpx.Response(200, json={"Authorization": f"token-{logins}"})

        requests += 1
        assert request.headers.get("Authorization") is None
        if requests == 1:
            assert request.headers.get("Token") == "token-1"
            return httpx.Response(419, json={"message": "Inactive session"})

        assert request.headers.get("Token") == "token-2"
        return httpx.Response(200, json=[])

    deductions = await make_client(handler).view_all_deductions("EMP-700")

    assert deductions == []
    assert logins == 2
    assert requests == 2
