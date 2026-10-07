from __future__ import annotations

import json
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError
from integrations.cdas_session import CdasSharedSession
from services.cdas_request_budget import CDAS_DAILY_REQUEST_LIMIT, _account_key


ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps" / "backend" / "routers" / "cdas_api.py"
CONFIG_SERVICE = ROOT / "apps" / "backend" / "services" / "cdas_config_service.py"


class MemorySessionBroker:
    def __init__(self) -> None:
        self.session: CdasSharedSession | None = None
        self.lock_entries = 0
        self.saves = 0
        self.clears = 0

    async def load(self) -> CdasSharedSession | None:
        return self.session

    async def save(self, session: CdasSharedSession) -> None:
        self.session = session
        self.saves += 1

    async def clear(self) -> None:
        self.session = None
        self.clears += 1

    @asynccontextmanager
    async def login_lock(self):
        self.lock_entries += 1
        yield


def make_client(handler, *, request_guard=None, session_broker=None) -> CdasClient:
    return CdasClient(
        base_url="https://cdas.test",
        username="test-user",
        password="test-password",
        transport=httpx.MockTransport(handler),
        request_guard=request_guard,
        session_broker=session_broker,
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

    assert await client.check_affordability("EMP-1") == Decimal("1500.50")
    assert reservations == 2  # login + first provider read

    assert await client.check_affordability("EMP-1") == Decimal("1500.50")
    assert reservations == 3  # cached token + second provider read only


@pytest.mark.asyncio
async def test_independent_clients_reuse_one_shared_session() -> None:
    broker = MemorySessionBroker()
    logins = 0
    reads = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal logins, reads
        if request.url.path == "/api/security/login":
            logins += 1
            return httpx.Response(200, json={"Authorization": "shared-token"})
        assert request.url.path == "/api/employee/check-affordability"
        reads += 1
        return httpx.Response(200, content=b"875.25")

    first = make_client(handler, session_broker=broker)
    second = make_client(handler, session_broker=broker)

    assert await first.check_affordability("EMP-1") == Decimal("875.25")
    assert await second.check_affordability("EMP-2") == Decimal("875.25")

    assert logins == 1
    assert reads == 2
    assert broker.lock_entries == 1
    assert broker.saves >= 3  # login persistence + last-used refreshes


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


def test_clean_company_client_wires_quota_guard_shared_session_and_local_status() -> None:
    router_source = ROUTER.read_text(encoding="utf-8")
    config_source = CONFIG_SERVICE.read_text(encoding="utf-8")

    assert '@router.get("/request-budget")' in router_source
    assert "get_cdas_request_budget_status" in router_source
    assert '"Return LoanHub\'s local CDAS quota counter without contacting CDAS."' in router_source
    assert "consume_cdas_request_budget" in config_source
    assert "request_guard=_request_guard(company_id, environment)" in config_source
    assert "RedisCdasSessionBroker" in config_source
    assert "session_broker=_shared_session_broker(credentials, generation=signature)" in config_source
    assert '"shared_session_enabled": bool(settings.REDIS_URL)' in config_source


def test_cdas_v15_provider_errors_are_structured_and_actionable() -> None:
    integration = (ROOT / "apps" / "backend" / "integrations" / "cdas.py").read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")

    for status, code in [
        (495, "DEDUCTION_MODIFICATION_DISALLOWED"),
        (496, "INVALID_INSTALLMENT_COUNT"),
        (497, "INVALID_EFFECTIVE_MONTH"),
        (498, "ITEM_CODE_OWNERSHIP_MISMATCH"),
        (499, "DEDUCTION_EXCEEDS_AFFORDABILITY"),
    ]:
        assert f'{status}: {{"code": "{code}"' in integration

    assert "cdas_error_semantics" in router
    assert '"provider_error_code": semantics["code"]' in router
    assert '"retryable": semantics["retryable"]' in router
    assert '"action": semantics["action"]' in router


def test_live_release_requires_exact_fresh_tested_profile_and_explicit_platform_approval() -> None:
    config_source = CONFIG_SERVICE.read_text(encoding="utf-8")
    platform_router = (ROOT / "apps" / "backend" / "routers" / "platform_cdas.py").read_text(encoding="utf-8")
    company_settings = (ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "settings" / "_components" / "company-cdas-settings.tsx").read_text(encoding="utf-8")
    platform_page = (ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "superadmin" / "control" / "integrations" / "cdas" / "page.tsx").read_text(encoding="utf-8")

    assert "LIVE_CONNECTION_TEST_MAX_AGE_HOURS = 24" in config_source
    assert "def _profile_release_fingerprint(" in config_source
    assert "def live_release_state(" in config_source
    assert "def approve_live_release(" in config_source
    assert "profile_fingerprint" in config_source
    assert "connection_test_fresh" in config_source
    assert "must explicitly approve this exact tested CDAS Live profile for production" in config_source
    assert '@router.post("/companies/{company_id}/live-release/approve")' in platform_router
    assert "Approve exact Live profile" in platform_page
    assert "CDAS production readiness" in company_settings


def test_cdas_readiness_is_explicit_blocking_and_non_authoritative_for_external_approval() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert '@router.get("/readiness")' in source
    assert '"api_contract": "v1.5"' in source
    assert '"10/10-ready"' in source
    assert '"mutation_reconciliation"' in source
    assert '"request_budget"' in source
    assert '"shared_session"' in source
    assert '"live_release"' in source
    assert '"live_test_fresh"' in source
    assert "does not itself grant DataNet/CDAS production permission" in source
