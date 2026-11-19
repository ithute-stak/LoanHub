"""Bulk job persistence contract: fail-closed state transitions."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from services.cdas_affordability_bulk_jobs import (
    batch_fingerprint, safe_batch_summary, transition_batch,
)


def selected(borrower, employee, amount):
    return SimpleNamespace(borrower_id=borrower, employee_number=employee,
                           proposed_monthly_installment=Decimal(amount))


def test_fingerprint_is_order_independent_and_normalized():
    a, b = uuid4(), uuid4()
    first = [selected(a, " EMP-1 ", "100.0"), selected(b, "EMP-2", "200.00")]
    second = [selected(b, "emp-2", "200"), selected(a, "emp-1", "100.00")]
    assert batch_fingerprint(first) == batch_fingerprint(second)


def test_fingerprint_differs_for_changed_installment():
    borrower = uuid4()
    assert batch_fingerprint([selected(borrower, "EMP-1", "100")]) != batch_fingerprint(
        [selected(borrower, "EMP-1", "101")]
    )


@pytest.mark.parametrize("status", ["queued", "running", "completed", "retrying", "draft"])
def test_provider_execution_transition_is_disabled(status):
    with pytest.raises(ValueError):
        transition_batch("draft", status)


def test_draft_can_be_cancelled_but_not_restarted():
    assert transition_batch("draft", "cancelled") == "cancelled"
    with pytest.raises(ValueError):
        transition_batch("cancelled", "draft")


def test_invalid_amount_is_rejected():
    with pytest.raises(ValueError):
        batch_fingerprint([selected(uuid4(), "EMP-1", "NaN")])


def test_safe_summary_hides_private_fields():
    batch = SimpleNamespace(id=uuid4(), status="draft", total_count=1, finished_count=0)
    item = SimpleNamespace(
        id=uuid4(), borrower_id=uuid4(), employee_number="EMP-100",
        status="pending", error_code=None, assessment_record_id=None,
        salary="secret", national_id="secret",
    )
    result = safe_batch_summary(batch, [item])
    assert result["execution_enabled"] is False
    assert "salary" not in result["items"][0]
    assert "national_id" not in result["items"][0]
