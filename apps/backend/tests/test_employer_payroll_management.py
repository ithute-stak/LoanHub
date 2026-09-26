from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException

from services.employer_payroll_service import _pay_date, money


ROOT = Path(__file__).resolve().parents[2]


def test_payroll_period_date_clamps_month_end_without_moving_period():
    assert _pay_date("2027-02", 31) == date(2027, 2, 28)
    assert _pay_date("2028-02", 31) == date(2028, 2, 29)
    assert _pay_date("2026-09", 25) == date(2026, 9, 25)


def test_payroll_period_requires_configured_day_or_explicit_date():
    with pytest.raises(HTTPException) as error:
        _pay_date("2026-09", None)
    assert error.value.status_code == 422
    assert "payroll day" in str(error.value.detail).lower()

    with pytest.raises(HTTPException):
        _pay_date("2026-09", 25, date(2026, 10, 1))


def test_payroll_money_rounds_to_ledger_precision():
    assert money("123.456") == Decimal("123.46")
    assert money(None) == Decimal("0.00")


def test_payroll_schema_is_company_scoped_and_preserves_audit_history():
    model = (ROOT / "backend" / "database" / "models" / "employer_payroll.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "g1m2p3r4s501_employer_payroll_management.py").read_text(encoding="utf-8")
    received_status = (ROOT / "backend" / "alembic" / "versions" / "g1m2p3r4s502_payroll_received_status.py").read_text(encoding="utf-8")

    assert 'ForeignKey("loan_companies.id", ondelete="CASCADE")' in model
    assert "uq_employer_payroll_account_company_group" in model
    assert "uq_employer_payroll_employee_account_number" in model
    assert "uq_employer_payroll_cycle_company_account_period" in model
    assert "uq_employer_payroll_deduction_cycle_source_key" in model
    assert 'down_revision = "f0l10a5e0001"' in migration
    assert 'down_revision = "g1m2p3r4s501"' in received_status
    assert "'received'" in received_status


def test_reconciliation_prefers_permanent_folio_and_never_guesses_ambiguous_employee_rows():
    source = (ROOT / "backend" / "services" / "employer_payroll_service.py").read_text(encoding="utf-8")

    assert "by_folio" in source
    assert 'line = by_folio.get(folio) if folio else None' in source
    assert "if len(candidates) == 1" in source
    assert 'status="unmatched"' in source
    assert "Could not uniquely match payroll row" in source
    assert 'cycle.status == "reconciled"' in source
    assert "Reconciled cycles are locked" in source


def test_employment_state_and_exception_rules_are_explicit():
    source = (ROOT / "backend" / "services" / "employer_payroll_service.py").read_text(encoding="utf-8")
    assert 'EMPLOYMENT_STATES = {"active", "suspended", "terminated", "left_employer"}' in source
    assert 'DEDUCTION_EXCEPTION_STATUSES = {"shortage", "excess", "rejected", "missing", "terminated", "unmatched"}' in source
    assert 'line.status = "missing"' in source
    assert 'line.status = "shortage"' in source
    assert 'line.status = "excess"' in source
    assert 'cycle.status = "exception" if exception_count else "reconciled"' in source


def test_employer_payroll_api_covers_full_operational_cycle():
    source = (ROOT / "backend" / "routers" / "employer_payroll.py").read_text(encoding="utf-8")
    api_router = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")

    assert 'APIRouter(prefix="/employer-payroll"' in source
    assert '@router.get("/overview")' in source
    assert '@router.put("/accounts")' in source
    assert '@router.put("/accounts/{account_id}/employees/{borrower_id}")' in source
    assert '@router.post("/accounts/{account_id}/cycles")' in source
    assert '@router.post("/cycles/{cycle_id}/import.csv")' in source
    assert '@router.post("/cycles/{cycle_id}/reconcile")' in source
    assert '@router.get("/exceptions")' in source
    assert '@router.get("/cycles/{cycle_id}/export.csv")' in source
    assert '@router.get("/cycles/{cycle_id}/export.pdf")' in source
    assert "employer_payroll.router" in api_router


def test_frontend_surfaces_exposure_cycles_exceptions_and_terminated_employees():
    page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "employer-payroll" / "page.tsx").read_text(encoding="utf-8")
    cycle_page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "employer-payroll" / "cycles" / "[cycleId]" / "page.tsx").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "api" / "employerPayroll.ts").read_text(encoding="utf-8")
    loan_nav = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "loans" / "layout.tsx").read_text(encoding="utf-8")

    assert "Employer & Payroll Management Centre" in page
    assert "Outstanding exposure" in page
    assert "Expected / month" in page
    assert "Exceptions requiring attention" in page
    assert "Employment-risk register" in page
    assert "Import employer CSV" in cycle_page
    assert "Permanent folio numbers are the primary matching key" in cycle_page
    assert "reconcilePayrollCycle" in api
    assert "/company/employer-payroll" in loan_nav
