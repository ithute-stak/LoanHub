from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from integrations.cdas import CdasClient


ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps" / "backend" / "routers" / "cdas_api.py"
CLIENT = ROOT / "apps" / "backend" / "integrations" / "cdas.py"


def make_client(handler) -> CdasClient:
    return CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_lifecycle_write_uses_documented_path_token_and_payload() -> None:
    request_payload = {
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
    observed: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-write"})
        observed["path"] = request.url.path
        observed["token"] = request.headers.get("Token")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(200, json={**request_payload, "DeductionStatus": 1})

    result = await make_client(handler).add_update_deduction(request_payload)

    assert observed == {
        "path": "/api/policy/add-update-deduction",
        "token": "token-write",
        "body": request_payload,
    }
    assert result["DeductionStatus"] == 1


@pytest.mark.asyncio
async def test_modify_active_uses_documented_path_and_payload() -> None:
    request_payload = {
        "EmployeeNo": "EMP-801",
        "ItemCode": "LOAN",
        "TotalInstallment": 10,
        "DeductionAmount": 450.0,
        "PrincipalAmount": 4500.0,
        "DeductionID": 81,
        "EffectiveDate": "2026-10-01",
    }
    observed: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-modify"})
        observed["path"] = request.url.path
        observed["token"] = request.headers.get("Token")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(200, json=request_payload)

    result = await make_client(handler).modify_active_deduction(request_payload)

    assert observed == {
        "path": "/api/policy/modify-active-deduction",
        "token": "token-modify",
        "body": request_payload,
    }
    assert result == request_payload


@pytest.mark.asyncio
async def test_settle_uses_documented_path_and_payload() -> None:
    request_payload = {
        "ItemCode": "LOAN",
        "DeductionID": 82,
        "EffectiveDate": "2026-10-01T00:00:00.000Z",
        "EmployeeNo": "EMP-802",
        "SettlementReason": 2,
    }
    observed: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-settle"})
        observed["path"] = request.url.path
        observed["token"] = request.headers.get("Token")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(200, json=request_payload)

    result = await make_client(handler).settle_deduction(request_payload)

    assert observed == {
        "path": "/api/policy/settled-deduction",
        "token": "token-settle",
        "body": request_payload,
    }
    assert result == request_payload


@pytest.mark.asyncio
async def test_document_request_preserves_official_documenttye_response_key() -> None:
    observed: dict[str, object] = {}
    provider_document = {
        "FileName": "statement.bin",
        "DocumentTye": "Statement",
        "Year": 2026,
        "Month": 9,
        "Content": "AQID",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-doc"})
        observed["path"] = request.url.path
        observed["token"] = request.headers.get("Token")
        observed["body"] = json.loads(request.read().decode())
        return httpx.Response(200, json=provider_document)

    result = await make_client(handler).get_document(year=2026, month=9, document_type=2)

    assert observed == {
        "path": "/api/policy/get_document",
        "token": "token-doc",
        "body": {"Year": 2026, "Month": 9, "DocumentType": 2},
    }
    assert result == provider_document
    assert "DocumentTye" in result


def test_state_changing_routes_require_management_confirmation_and_audit() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    for route in (
        '/deductions/lifecycle',
        '/deductions/modify-active',
        '/deductions/settle',
    ):
        assert route in source

    assert source.count("_require_company_manager(context)") >= 7
    assert source.count("_require_confirmed(payload.confirmed)") == 3
    assert "Explicit confirmation is required for this CDAS state-changing action" in source
    assert "AuditLog(" in source
    assert 'action="cdas.deduction.lifecycle"' in source
    assert 'action="cdas.deduction.modify_active"' in source
    assert 'action="cdas.deduction.settle"' in source


def test_all_provider_mutations_explicitly_disable_automatic_session_replay() -> None:
    source = CLIENT.read_text(encoding="utf-8")

    assert source.count("retry_expired_session=False") == 3
    assert "A mutation must never be replayed automatically" in source
