"""Compensation must restore the exact original installment status."""
import pytest
from fastapi import HTTPException
from database.models.enums import InstallmentStatus
from services.rollover_compensation_posting import restore_original_rollover_installment_status


@pytest.mark.parametrize("state", ["pending", "partially_paid", "overdue"])
def test_restore_original_open_state(state):
    assert restore_original_rollover_installment_status({"installment_status": state}) == InstallmentStatus(state)


@pytest.mark.parametrize("snapshot", [{}, {"installment_status": "paid"}, {"installment_status": "waived"}, {"installment_status": "invalid"}])
def test_invalid_or_closed_state_rejected(snapshot):
    with pytest.raises(HTTPException) as error:
        restore_original_rollover_installment_status(snapshot)
    assert error.value.status_code == 409
