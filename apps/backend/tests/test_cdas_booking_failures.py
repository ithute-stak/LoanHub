from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.cdas_booking_failures import (
    build_failure_workspace,
    normalize_failure_reason,
    record_booking_failure,
    reopen_failed_opportunity,
    retry_is_due,
)


NOW = datetime(2026, 9, 15, 8, 0, 0)


def _failure(**overrides):
    values = {
        "id": uuid4(),
        "opportunity_id": uuid4(),
        "reason_code": "cdas_rejected",
        "reason_details": "Payroll returned a rejection.",
        "failed_at": NOW - timedelta(days=1),
        "retry_eligible": True,
        "retry_after": NOW - timedelta(hours=1),
        "created_by_user_id": uuid4(),
        "created_at": NOW - timedelta(days=1),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_failure_reason_is_controlled():
    assert normalize_failure_reason("CDAS_REJECTED") == "cdas_rejected"
    with pytest.raises(ValueError, match="Unsupported"):
        normalize_failure_reason("random reason")


def test_retry_due_respects_eligibility_and_retry_time():
    assert retry_is_due({"retry_eligible": True, "retry_after": None}, now=NOW) is True
    assert retry_is_due({"retry_eligible": True, "retry_after": NOW - timedelta(minutes=1)}, now=NOW) is True
    assert retry_is_due({"retry_eligible": True, "retry_after": NOW + timedelta(minutes=1)}, now=NOW) is False
    assert retry_is_due({"retry_eligible": False, "retry_after": None}, now=NOW) is False


def test_failure_workspace_preserves_history_and_exposes_recordable_opportunities():
    failed_id = uuid4()
    active_id = uuid4()
    booked_id = uuid4()
    failures = [
        _failure(opportunity_id=failed_id, failed_at=NOW - timedelta(days=1)),
        _failure(opportunity_id=failed_id, failed_at=NOW - timedelta(days=5), retry_eligible=False, retry_after=None),
    ]
    opportunities = [
        {"id": str(failed_id), "pipeline_stage": "failed", "state": "FAILED", "client_name": "Failed Client", "opportunity_deduction_amount": 900},
        {"id": str(active_id), "pipeline_stage": "booking_submitted", "state": "UPCOMING", "client_name": "Active Client", "opportunity_deduction_amount": 1200},
        {"id": str(booked_id), "pipeline_stage": "booked", "state": "BOOKED", "client_name": "Booked Client", "opportunity_deduction_amount": 1500},
    ]

    result = build_failure_workspace(opportunities, failures, now=NOW)

    assert result["summary"]["failure_attempts"] == 2
    assert result["summary"]["currently_failed"] == 1
    assert result["summary"]["retry_due"] == 1
    assert result["items"][0]["failure_count"] == 2
    assert result["items"][0]["latest_failure"]["failed_at"] == NOW - timedelta(days=1)
    assert [item["id"] for item in result["recordable_opportunities"]] == [str(active_id)]


def test_already_failed_opportunity_must_be_reopened_before_another_failure():
    item = SimpleNamespace(status="monitoring", pipeline_stage="failed")
    with pytest.raises(ValueError, match="already failed"):
        record_booking_failure(
            SimpleNamespace(),
            item=item,
            company_id=uuid4(),
            user_id=uuid4(),
            reason_code="other",
            reason_details=None,
            failed_at=NOW,
            retry_eligible=False,
            retry_after=None,
        )


def test_reopen_requires_retryable_latest_failure_and_due_date():
    item = SimpleNamespace(status="monitoring", pipeline_stage="failed")
    with pytest.raises(ValueError, match="not marked retryable"):
        reopen_failed_opportunity(
            SimpleNamespace(),
            item=item,
            latest_failure=_failure(retry_eligible=False, retry_after=None),
            user_id=uuid4(),
            now=NOW,
        )

    with pytest.raises(ValueError, match="retry date"):
        reopen_failed_opportunity(
            SimpleNamespace(),
            item=item,
            latest_failure=_failure(retry_eligible=True, retry_after=NOW + timedelta(days=1)),
            user_id=uuid4(),
            now=NOW,
        )
