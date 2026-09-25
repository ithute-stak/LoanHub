from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from integrations.cdas import CdasClient
from integrations.cdas_contracts import CdasLifecyclePayload, CdasModifyActivePayload


ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps" / "backend" / "routers" / "cdas_api.py"
CLIENT = ROOT / "apps" / "backend" / "integrations" / "cdas.py"
CONTRACTS = ROOT / "apps" / "backend" / "integrations" / "cdas_contracts.py"


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


def test_lifecycle_contract_accepts_only_supported_codes_and_uses_decimal_money() -> None:
    route_source = ROUTER.read_text(encoding="utf-8")
    contract_source = CONTRACTS.read_text(encoding="utf-8")

    payload = CdasLifecyclePayload(
        request_type=1,
        deduction_id=0,
        employee_no=" EMP-900 ",
        loan_policy=1,
        item_code=" LOAN ",
        deduction_amount="500.10",
        total_installment=12,
        principal_amount="6001.20",
        effective_month="2026-10",
        reference_no=" REF-900 ",
    )

    assert payload.deduction_amount == Decimal("500.10")
    assert payload.principal_amount == Decimal("6001.20")
    assert payload.provider_payload()["DeductionAmount"] == 500.1
    assert payload.provider_payload()["PrincipalAmount"] == 6001.2
    assert payload.ledger_payload()["DeductionAmount"] == "500.10"
    assert payload.ledger_payload()["PrincipalAmount"] == "6001.20"
    assert payload.provider_payload()["EmployeeNo"] == "EMP-900"

    assert "request_type: Literal[1, 3, 4, 6, 10]" in contract_source
    assert "loan_policy: Literal[1, 2]" in contract_source
    assert "class CdasDeductionLifecycleRequest(CdasLifecyclePayload)" in route_source
    assert "deduction_amount: float" not in route_source
    assert "principal_amount: float" not in route_source


def test_modify_contract_keeps_exact_money_until_provider_boundary() -> None:
    payload = CdasModifyActivePayload(
        employee_no="EMP-901",
        item_code="LOAN",
        total_installment=10,
        deduction_amount="450.25",
        principal_amount="4502.50",
        deduction_id=91,
        effective_date="2026-10-01",
    )

    assert payload.deduction_amount == Decimal("450.25")
    assert payload.provider_payload()["DeductionAmount"] == 450.25
    assert payload.ledger_payload()["PrincipalAmount"] == "4502.50"


def test_all_provider_mutations_explicitly_disable_automatic_session_replay() -> None:
    source = CLIENT.read_text(encoding="utf-8")
    methods = (
        "add_update_deduction",
        "modify_active_deduction",
        "settle_deduction",
    )

    for index, method in enumerate(methods):
        start = source.index(f"    async def {method}(")
        if index + 1 < len(methods):
            end = source.index(f"    async def {methods[index + 1]}(", start)
        else:
            end = source.index("    async def get_document(", start)
        assert "retry_expired_session=False" in source[start:end]

    assert "A mutation must never be replayed automatically" in source
