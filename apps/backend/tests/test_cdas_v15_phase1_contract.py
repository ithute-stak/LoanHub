"""Phase 1: isolated provider-v1.5 examples and error-boundary tests.

No live CDAS network traffic. All requests pass through httpx.MockTransport.
"""
from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError
from integrations.cdas_contracts import validate_deduction, validate_deduction_write, validate_document


def client(handler):
    return CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_employee_details_match_v15_fields_and_auth_header():
    seen = []

    async def handler(request):
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "session-token"})
        seen.append((request.url.path, request.headers.get("Authorization"), json.loads(request.content)))
        return httpx.Response(200, json={
            "EmployeeNo": "00012345", "Name": "Test", "Surname": "Employee",
            "DOB": "1991-01-01", "Department": "Public Service",
            "JoiningDate": "2015-01-01", "TerminationDate": None,
        })

    result = await client(handler).get_employee_details(" 00012345 ")
    assert seen == [("/api/employee/getDetails", "session-token", {"EmployeeNo": "00012345"})]
    assert result["EmployeeNo"] == "00012345"
    assert result["Department"] == "Public Service"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [
    (429, "Maximum request threshold reached"),
    (404, "Employee not found"),
])
async def test_employee_lookup_preserves_provider_failure(status, expected):
    async def handler(request):
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token"})
        return httpx.Response(status, json={"message": expected})

    with pytest.raises(CdasError) as raised:
        await client(handler).get_employee_details("EMP-2")
    assert raised.value.status_code == status
    assert expected in str(raised.value)


@pytest.mark.asyncio
async def test_affordability_accepts_documented_numeric_zero():
    async def handler(request):
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token"})
        assert request.url.path == "/api/employee/check-affordability"
        assert request.headers["Token"] == "token"
        return httpx.Response(200, json=0.0)

    assert await client(handler).check_affordability("EMP-2") == Decimal("0.0")


@pytest.mark.asyncio
async def test_deduction_reads_handle_empty_provider_arrays():
    async def handler(request):
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token"})
        assert request.headers["Token"] == "token"
        return httpx.Response(200, json=[])

    service = client(handler)
    assert await service.view_all_deductions("EMP-2") == []
    assert await service.view_own_deductions("EMP-2", 5) == []


@pytest.mark.asyncio
async def test_document_not_ready_406_is_exposed_without_auth_replay():
    logins = 0
    document_calls = 0

    async def handler(request):
        nonlocal logins, document_calls
        if request.url.path == "/api/security/login":
            logins += 1
            return httpx.Response(200, json={"Authorization": f"token-{logins}"})
        assert request.url.path == "/api/policy/get_document"
        document_calls += 1
        return httpx.Response(406, json={"message": "Reports not ready yet"})

    with pytest.raises(CdasError) as raised:
        await client(handler).get_document(year=2026, month=10, document_type=2)
    assert raised.value.status_code == 406
    assert "Reports not ready yet" in raised.value.message
    assert logins == 1
    assert document_calls == 1


def test_document_accepts_documented_typo_and_content():
    assert validate_document({
        "FileName": "statement.csv", "DocumentTye": "Statement",
        "Year": 2026, "Month": 10, "Content": [65, 66],
    })["Content"] == [65, 66]


def test_deduction_response_currently_allows_sparse_object_audit_gap():
    # Documents an observed lenient contract; should become endpoint-specific.
    assert validate_deduction({}) == {}


@pytest.mark.parametrize("payload", [{}, {"DeductionID": 0, "EmployeeNo": "EMP-1"}, {"DeductionID": 42}, {"DeductionID": True, "EmployeeNo": "EMP-1"}])
def test_write_confirmation_rejects_missing_deduction_identity(payload):
    with pytest.raises(ValueError):
        validate_deduction_write(payload)


def test_write_confirmation_preserves_valid_response():
    payload = {"DeductionID": 42, "EmployeeNo": "EMP-1", "DeductionStatus": 3}
    assert validate_deduction_write(payload) == payload


@pytest.mark.asyncio
async def test_write_success_without_deduction_identity_fails_safely_without_retry():
    writes = 0

    async def handler(request):
        nonlocal writes
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token"})
        writes += 1
        return httpx.Response(200, json={})

    with pytest.raises(CdasError) as raised:
        await client(handler).settle_deduction({
            "ItemCode": "LOAN", "DeductionID": 42,
            "EmployeeNo": "EMP-1", "EffectiveDate": "2026-10-23",
            "SettlementReason": 2,
        })
    assert raised.value.status_code == 502
    assert writes == 1
