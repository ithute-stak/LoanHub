"""Regressions for the top-up settlement and owner-approval boundary."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVAL = (ROOT / "routers/professional_lending.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/marketplace/_components/internal-applications-workspace.tsx").read_text()


def test_approval_uses_earned_interest_quote_not_scheduled_balance():
    section = APPROVAL.split("def approve_direct(", 1)[1].split(
        '@router.post("/direct-applications/{application_id}/reject")', 1
    )[0]
    assert "preview_top_up_settlement(" in section
    assert "top_up_settlement_amount = Decimal(quote.settlement_amount)" in section
    assert "top_up_cash_amount = Decimal(application.top_up_cash_requested or 0)" in section
    assert "expected_principal = replacement_principal(quote, top_up_cash_amount)" in section
    assert 'top_up_settlement_amount = Decimal(parent_loan.balance)' not in section
    assert "Recalculate the draft top-up" in section
    assert 'application.status not in {"submitted", "under_review"}' in section


def test_draft_can_only_continue_to_assessment_not_approve():
    assert 'selected.status === "draft"' in UI
    assert "Complete assessment and submit draft" in UI
    assert 'canApprove && ["submitted", "under_review"].includes(selected.status)' in UI
    assert 'Application is not awaiting approval' in APPROVAL
