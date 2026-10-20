"""Regression guardrails for draft-only top-up repayment rescheduling."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = (ROOT / "routers/origination.py").read_text()
FRONTEND = (
    ROOT.parent / "frontend/app/(dashboard)/company/origination/new/page.tsx"
).read_text()


def test_original_dates_audited_and_assessment_invalidated():
    assert 'action="top_up.installments_rescheduled"' in ROUTER
    assert '"original_due_dates": previous_due_dates' in ROUTER
    assert '"revised_due_dates": resolved_due_dates' in ROUTER
    assert 'application.affordability_assessment_id = None' in ROUTER
    assert 'application.status != "draft" or application.loan_id is not None' in ROUTER


def test_reschedule_requires_confirmation():
    assert "generateMonthlyInstallmentDueDates" in FRONTEND
    assert "confirmTopUpReschedule" in FRONTEND
    assert "Preview revised schedule" in FRONTEND
    assert "Confirm rescheduled dates" in FRONTEND
    assert "setAssessment(null)" in FRONTEND
