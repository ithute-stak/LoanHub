"""Bulk preflight must never trigger provider requests or mutate loans."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers import cdas_government_employees as mod


def selection(borrower_id=None, number="EMP-100", installment="100.00"):
    return mod.BulkAffordabilitySelection(
        borrower_id=borrower_id or uuid4(),
        employee_number=number,
        proposed_monthly_installment=installment,
    )


def test_duplicate_employee_number_rejected_even_when_case_differs():
    errors = mod.validate_bulk_selection([
        selection(number="EMP-100"), selection(number=" emp-100 "),
    ])
    assert "duplicate_employee_number_selection" in errors


def test_duplicate_borrower_rejected():
    bid = uuid4()
    errors = mod.validate_bulk_selection([
        selection(borrower_id=bid, number="EMP-1"),
        selection(borrower_id=bid, number="EMP-2"),
    ])
    assert "duplicate_borrower_selection" in errors


def test_batch_size_capped_to_twenty():
    with pytest.raises(Exception):
        mod.BulkAffordabilityPreflightRequest(
            employees=[selection(number=f"EMP-{i}") for i in range(21)],
        )


def test_preflight_never_contacts_cdas_or_queues_jobs(monkeypatch):
    company = uuid4()
    ctx = SimpleNamespace(company_id=company, staff=object(),
                          is_platform_admin=False)
    monkeypatch.setattr(mod, "_require_company_manager", lambda context: None)
    monkeypatch.setattr(mod, "_company_cdas_environment", lambda db, company_id: "test")
    monkeypatch.setattr(mod, "get_cdas_request_budget_status",
                        lambda db, company_id, environment: {"remaining": 100})
    monkeypatch.setattr(mod, "_bulk_candidate_status",
                        lambda db, company_id, selection: "ready_for_live_verification")

    class Query:
        def filter(self, *args):
            return self
        def first(self):
            return SimpleNamespace(is_active=True)
    class DB:
        def query(self, model):
            return Query()
        def add(self, *args):
            raise AssertionError("preflight must not write")
        def commit(self):
            raise AssertionError("preflight must not commit")

    request = mod.BulkAffordabilityPreflightRequest(
        employees=[selection(number="EMP-1"), selection(number="EMP-2")],
    )
    result = mod.preflight_bulk_government_affordability(
        payload=request, context=ctx, db=DB(),
    )
    assert result["execution_enabled"] is False
    assert result["batch_created"] is False
    assert result["provider_contacted"] is False
    assert result["minimum_estimated_provider_requests"] == 4
    assert result["ready_count"] == 2


def test_non_positive_installment_rejected():
    with pytest.raises(Exception):
        selection(installment="0")
