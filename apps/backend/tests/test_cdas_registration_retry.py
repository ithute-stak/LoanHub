from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from routers.cdas_lifecycle import CdasRegistrationRetryRequest
from services.cdas_registration_retry import _provider_failure_is_safe_to_retry


@pytest.mark.parametrize("status", [400, 404, 409, 429, 495, 496, 497, 498, 499])
def test_confirmed_provider_rejections_are_retry_safe(status: int):
    assert _provider_failure_is_safe_to_retry(status) is True


@pytest.mark.parametrize("status", [None, 401, 402, 500, 502, 503])
def test_uncertain_provider_failures_are_not_retry_safe(status: int | None):
    assert _provider_failure_is_safe_to_retry(status) is False


def test_registration_retry_payload_validates_correctable_fields():
    payload = CdasRegistrationRetryRequest(
        item_code="ITEM",
        reference_no="LH-REF-001",
        loan_policy=1,
        deduction_amount=Decimal("500.00"),
        principal_amount=Decimal("6000.00"),
        total_installment=12,
        effective_month="2026-10",
    )
    assert payload.total_installment == 12
    assert payload.effective_month == "2026-10"


@pytest.mark.parametrize("effective_month", ["10/2026", "2026-00", "2026-13"])
def test_registration_retry_rejects_invalid_effective_month(effective_month: str):
    with pytest.raises(ValidationError):
        CdasRegistrationRetryRequest(
            item_code="ITEM",
            reference_no="LH-REF-001",
            loan_policy=1,
            deduction_amount=Decimal("500.00"),
            principal_amount=Decimal("6000.00"),
            total_installment=12,
            effective_month=effective_month,
        )
