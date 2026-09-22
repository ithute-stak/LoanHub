import asyncio
import json

import httpx

from services.cdas_api_client import (
    CdasApiClient,
    CdasDeductionStatus,
    CdasRequestType,
)


def _run(coro):
    return asyncio.run(coro)


def test_employee_details_uses_documented_authorization_header_and_token_is_reused() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/security/login":
            assert json.loads(request.content) == {
                "Username": "integration-user",
                "Password": "integration-password",
            }
            return httpx.Response(200, json={"Authorization": "token-1"})

        if request.url.path == "/api/employee/getDetails":
            assert request.headers.get("Authorization") == "token-1"
            assert request.headers.get("Token") is None
            assert json.loads(request.content) == {"EmployeeNo": "EMP001"}
            return httpx.Response(
                200,
                json={
                    "EmployeeNo": "EMP001",
                    "Name": "Test",
                    "Surname": "Employee",
                },
            )

        if request.url.path == "/api/employee/check-affordability":
            assert request.headers.get("Token") == "token-1"
            assert json.loads(request.content) == {"EmployeeNo": "EMP001"}
            return httpx.Response(200, json=2500.0)

        return httpx.Response(500, json={"message": "unexpected request"})

    async def scenario() -> None:
        client = CdasApiClient(
            base_url="https://cdas.test",
            username="integration-user",
            password="integration-password",
            transport=httpx.MockTransport(handler),
        )
        employee = await client.get_employee("EMP001")
        affordability = await client.check_affordability("EMP001")
        await client.aclose()

        assert employee["EmployeeNo"] == "EMP001"
        assert affordability == 2500.0

    _run(scenario())
    assert [request.url.path for request in requests].count("/api/security/login") == 1


def test_expired_token_is_reauthenticated_once_for_401() -> None:
    login_count = 0
    employee_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count, employee_attempts
        if request.url.path == "/api/security/login":
            login_count += 1
            return httpx.Response(200, json={"Authorization": f"token-{login_count}"})

        if request.url.path == "/api/employee/getDetails":
            employee_attempts += 1
            if employee_attempts == 1:
                assert request.headers["Authorization"] == "token-1"
                return httpx.Response(401, json={"message": "token expired"})
            assert request.headers["Authorization"] == "token-2"
            return httpx.Response(200, json={"EmployeeNo": "EMP002"})

        return httpx.Response(500)

    async def scenario() -> None:
        client = CdasApiClient(
            base_url="https://cdas.test",
            username="integration-user",
            password="integration-password",
            transport=httpx.MockTransport(handler),
        )
        payload = await client.get_employee("EMP002")
        await client.aclose()
        assert payload == {"EmployeeNo": "EMP002"}

    _run(scenario())
    assert login_count == 2
    assert employee_attempts == 2


def test_policy_operations_use_token_header_and_exact_cdas_field_names() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "policy-token"})
        captured["path"] = request.url.path
        captured["token"] = request.headers.get("Token")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"DeductionID": 99})

    async def scenario() -> None:
        client = CdasApiClient(
            base_url="https://cdas.test",
            username="integration-user",
            password="integration-password",
            transport=httpx.MockTransport(handler),
        )
        response = await client.add_update_deduction(
            request_type=int(CdasRequestType.REGISTRATION),
            deduction_id=0,
            employee_no="EMP003",
            loan_policy=1,
            item_code="ITEM01",
            deduction_amount=500.25,
            total_installment=12,
            principal_amount=6003.0,
            effective_month="2026-10",
            reference_no="LH-0003",
        )
        await client.aclose()
        assert response == {"DeductionID": 99}

    _run(scenario())
    assert captured == {
        "path": "/api/policy/add-update-deduction",
        "token": "policy-token",
        "body": {
            "RequestType": 1,
            "DeductionID": 0,
            "EmployeeNo": "EMP003",
            "LoanPolicy": 1,
            "ItemCode": "ITEM01",
            "DeductionAmount": 500.25,
            "TotalInstallment": 12,
            "PrincipalAmount": 6003.0,
            "EffectiveMonth": "2026-10",
            "ReferenceNo": "LH-0003",
        },
    }


def test_documented_duplicate_code_values_are_preserved_as_enum_aliases() -> None:
    assert int(CdasRequestType.REJECT) == 6
    assert int(CdasRequestType.CANCELLED) == 6
    assert int(CdasRequestType.AUTO_SETTLED) == 8
    assert int(CdasRequestType.EXPIRED) == 8
    assert int(CdasDeductionStatus.AUTO_SETTLED) == 8
    assert int(CdasDeductionStatus.EXPIRED) == 8
