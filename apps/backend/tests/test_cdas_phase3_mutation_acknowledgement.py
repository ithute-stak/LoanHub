"""Phase 3: guard CDAS mutation acknowledgement identity against wrong borrower/deduction."""
import httpx
import pytest

from integrations.cdas import CdasClient, CdasError


@pytest.mark.asyncio
@pytest.mark.parametrize("operation,returned,expected_message", [
    ("add", {"DeductionID": 501, "EmployeeNo": "OTHER"}, "employee number"),
    ("modify", {"DeductionID": 999, "EmployeeNo": "EMP-1"}, "deduction ID"),
    ("settle", {"DeductionID": 999, "EmployeeNo": "EMP-1"}, "deduction ID"),
])
async def test_wrong_provider_acknowledgement_identity_is_rejected_without_mutation_replay(
    operation, returned, expected_message
):
    writes = 0

    async def handler(request):
        nonlocal writes
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token"})
        writes += 1
        return httpx.Response(200, json=returned)

    service = CdasClient(
        base_url="https://cdas.test", username="user", password="password",
        transport=httpx.MockTransport(handler),
    )
    request = {"EmployeeNo": "EMP-1", "DeductionID": 501}
    with pytest.raises(CdasError) as error:
        if operation == "add":
            await service.add_update_deduction(request)
        elif operation == "modify":
            await service.modify_active_deduction(request)
        else:
            await service.settle_deduction(request)
    assert error.value.status_code == 502
    assert expected_message in error.value.message
    assert writes == 1


@pytest.mark.asyncio
async def test_registration_accepts_provider_assigned_deduction_id():
    async def handler(request):
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token"})
        return httpx.Response(200, json={"DeductionID": 52, "EmployeeNo": "EMP-1"})

    service = CdasClient(
        base_url="https://cdas.test", username="user", password="password",
        transport=httpx.MockTransport(handler),
    )
    result = await service.add_update_deduction({"EmployeeNo": "EMP-1", "DeductionID": 0})
    assert result["DeductionID"] == 52


@pytest.mark.asyncio
async def test_non_registration_lifecycle_requires_same_existing_deduction_id():
    async def handler(request):
        if request.url.path == "/api/security/login":
            return httpx.Response(200, json={"Authorization": "token"})
        return httpx.Response(200, json={"DeductionID": 99, "EmployeeNo": "EMP-1"})

    service = CdasClient(
        base_url="https://cdas.test", username="user", password="password",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(CdasError) as error:
        await service.add_update_deduction({
            "EmployeeNo": "EMP-1", "DeductionID": 52, "RequestType": 4,
        })
    assert error.value.status_code == 502
    assert "deduction ID" in error.value.message
