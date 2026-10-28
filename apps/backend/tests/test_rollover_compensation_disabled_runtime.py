"""An unverified compensating reversal must never query or mutate the DB."""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from services.rollover_compensation_posting import post_rollover_compensation


class NoDatabaseCalls:
    def __getattr__(self, name):
        raise AssertionError(f"Compensation touched DB while disabled: {name}")


def test_compensation_is_disabled_before_database_access():
    with pytest.raises(HTTPException) as err:
        post_rollover_compensation(
            NoDatabaseCalls(), company_id=uuid4(), transfer_id=uuid4(),
            actor_user_id=uuid4(), independent_approver_id=uuid4(),
            reference="REV-001", approval_reference="APPROVED-001",
            reason="Contract correction",
        )
    assert err.value.status_code == 503
