"""Regression contracts for cancelling an unprocessed top-up after parent settlement."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROUTER = (BACKEND / "routers/origination.py").read_text()
PAGE = (BACKEND.parent / "frontend/app/(dashboard)/company/loans/top-up/page.tsx").read_text()
API = (BACKEND.parent / "frontend/api/origination.ts").read_text()


def _section(name):
    return ROUTER.split(f"def {name}(", 1)[1].split("@router.", 1)[0]


def test_rejection_is_authorized_audited_and_not_a_loan_mutation():
    section = _section("reject_top_up")
    assert "UserRole.COMPANY_OWNER" in section
    assert "UserRole.BRANCH_MANAGER" in section
    assert "_application(db, context=context, application_id=application_id, lock=True)" in section
    assert 'application.status not in {"draft", "submitted", "under_review"}' in section
    assert "application.loan_id is not None or application.approved_at is not None" in section
    assert 'application.status = "rejected"' in section
    assert 'action="top_up.application_rejected"' in section
    assert '"parent_status":' in section
    assert "db.delete(" not in section
    assert "parent.status =" not in section


def test_settled_parent_cannot_be_submitted_or_exception_approved():
    for name in ("submit_application", "approve_top_up_exception"):
        section = _section(name)
        assert "LoanStatus.ACTIVE, LoanStatus.DEFAULTED" in section
        assert "Decimal(parent.balance or 0) <= 0" in section
        assert "with_for_update()" in section


def test_direct_topup_screen_offers_rejection_and_disables_submission():
    assert "originationApi.rejectTopUp(application.id, reason.trim())" in PAGE
    assert "Reject top-up application" in PAGE
    assert "!parentEligible" in PAGE
    assert "window.confirm(" in PAGE
    assert "/reject-top-up" in API
