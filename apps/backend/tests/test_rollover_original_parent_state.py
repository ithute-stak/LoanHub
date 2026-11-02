"""A compensating reversal restores delinquency state from posting-time evidence."""
import pytest
from fastapi import HTTPException
from database.models.enums import LoanStatus
from services.rollover_compensation_posting import restore_original_rollover_parent_state


@pytest.mark.parametrize("overdue", [True, False])
def test_restore_original_active_parent_state(overdue):
    status, flag = restore_original_rollover_parent_state({
        "loan_status": "active", "loan_is_overdue": overdue,
    })
    assert status == LoanStatus.ACTIVE
    assert flag is overdue


@pytest.mark.parametrize("original", [
    {}, {"loan_status": "active"},
    {"loan_is_overdue": True},
    {"loan_status": "completed", "loan_is_overdue": False},
    {"loan_status": "active", "loan_is_overdue": "false"},
    {"loan_status": "invalid", "loan_is_overdue": False},
])
def test_reversal_rejects_missing_or_invalid_parent_snapshot(original):
    with pytest.raises(HTTPException) as exc:
        restore_original_rollover_parent_state(original)
    assert exc.value.status_code == 409
