"""Phase 2: CDAS affordability must be a usable currency capacity value."""
from decimal import Decimal

import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [-1, "-0.01", "NaN", "Infinity", "-Infinity"])
async def test_cdas_affordability_rejects_negative_or_nonfinite_provider_numbers(payload):
    async def handler(request):
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "test-token"})
        assert request.url.path == "/api/employee/check-affordability"
        return httpx.Response(200, json=payload)

    client = CdasClient(
        base_url="https://cdas.test", username="tester", password="test-only",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CdasError) as raised:
        await client.check_affordability("EMP-100")
    assert raised.value.status_code == 502


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,expected", [(0, Decimal("0")), (1000.25, Decimal("1000.25"))])
async def test_cdas_affordability_accepts_finite_nonnegative_numbers(payload, expected):
    async def handler(request):
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "test-token"})
        return httpx.Response(200, json=payload)

    client = CdasClient(
        base_url="https://cdas.test", username="tester", password="test-only",
        transport=httpx.MockTransport(handler),
    )
    assert await client.check_affordability("EMP-100") == expected
