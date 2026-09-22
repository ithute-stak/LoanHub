from __future__ import annotations

import pytest
from pydantic import ValidationError

from routers.cdas_api import CdasDeductionActionRequest


BASE_ACTION = {
    "deduction_id": 0,
    "employee_no": "EMP001",
    "loan_policy": 1,
    "item_code": "ITEM",
    "deduction_amount": 500.0,
    "total_installment": 12,
    "principal_amount": 6000.0,
    "effective_month": "2026-10",
    "reference_no": "REF-001",
}


@pytest.mark.parametrize("request_type", [1, 3, 4, 5, 6, 7, 8, 9, 10])
def test_documented_cdas_request_types_are_accepted(request_type: int):
    request = CdasDeductionActionRequest(request_type=request_type, **BASE_ACTION)
    assert request.request_type == request_type


def test_undocumented_cdas_request_type_two_is_rejected():
    with pytest.raises(ValidationError):
        CdasDeductionActionRequest(request_type=2, **BASE_ACTION)
