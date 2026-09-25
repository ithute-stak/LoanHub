from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError
from services.cdas_request_budget import CDAS_DAILY_REQUEST_LIMIT, _account_key


ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps" / "backend" / "routers" / "cdas_api.py"
CONFIG_SERVICE = ROOT / "apps" / "backend" / "services" / "cdas_config_service.py"


def make_client(handler, *, request_guard=None) -> CdasClient:
    return CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
        request_guard=request_guard,
    )


def test_request_budget_account_key_is_normalized_and_non_reversible() -> None:
    first = _account_key(" Lelefa.API.User ", "TEST")
    second = _account_key("lelefa.api.user", "test")

    assert first == second
    assert len(first) == 64
    assert "lelefa" not in first
    assert CDAS_DAILY_REQUEST_LIMIT == 400


@pytest.mark.asyncio
async def test_request_guard_reserves_login_and_each_provider_http_call() -> None:
    reservations = 0

    def reserve() -> None:
        nonlocal reservations
        reservations += 1

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token-guard"})
        assert request.url.path == "/api/employee/check-affordability"
        return httpx.Response(200, content=b"1500.50")

    client = make_client(handler, request_guard=reserve)

    assert await client.check_affordability("EMP-1") == 1500.5
    assert reservations == 2  # login + first provider read

    assert await client.check_affordability("EMP-1") == 1500.5
    assert reservations == 3  # cached token + second provider read only


@pytest.mark.asyncio
async def test_state_changing_request_is_not_replayed_after_inactive_session() -> None:
    logins = 0
    writes = 0
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

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins, writes
        if request.url.path == "/api/security/login":
            logins += 1
            return httpx.Response(200, json={"Authorization": f"token-{logins}"})

        assert request.url.path == "/api/policy/add-update-deduction"
        assert json.loads(request.read().decode()) == request_payload
        writes += 1
        if writes == 1:
            return httpx.Response(419, json={"message": "Inactive session"})
        return httpx.Response(200, json={**request_payload, "DeductionStatus": 1})

    client = make_client(handler)

    with pytest.raises(CdasError) as raised:
        await client.add_update_deduction(request_payload)

    assert raised.value.status_code == 419
    assert logins == 1
    assert writes == 1

    # The next deliberately initiated action starts a fresh session. The failed
    # mutation above was never automatically replayed.
    result = await client.add_update_deduction(request_payload)
    assert result["DeductionStatus"] == 1
    assert logins == 2
    assert writes == 2


def test_clean_company_client_wires_quota_guard_and_exposes_local_status_only() -> None:
    router_source = ROUTER.read_text(encoding="utf-8")
    config_source = CONFIG_SERVICE.read_text(encoding="utf-8")

    assert '@router.get("/request-budget")' in router_source
    assert "get_cdas_request_budget_status" in router_source
    assert '"Return LoanHub\'s local CDAS quota counter without contacting CDAS."' in router_source
    assert "consume_cdas_request_budget" in config_source
    assert "request_guard=_request_guard(company_id, credentials.environment)" in config_source
