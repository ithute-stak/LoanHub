from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_quick_loan_offer_requires_affordability_before_approval() -> None:
    router = _read(ROOT / "routers/loan_offers.py")
    service = _read(ROOT / "services/quick_loan_affordability_service.py")

    assert '@router.post("/quick-affordability-preview")' in router
    assert "_quick_affordability_for_terms(" in router
    assert 'if not affordability["passed"]:' in router
    assert "The borrower did not pass affordability for these offer terms." in router
    assert "def quick_loan_affordability(" in service
    assert '"decision": "pass" if passed else "fail"' in service
    assert '"maximum_affordable_installment"' in service
    assert '"disposable_after_installment"' in service
    assert '"dti_percent"' in service


def test_failed_quick_affordability_needs_authorized_own_risk_override() -> None:
    router = _read(ROOT / "routers/loan_offers.py")

    assert "payload.approve_at_own_risk" in router
    assert "context.role not in COMPANY_MANAGEMENT_ROLES" in router
    assert "policy.manager_override_enabled" in router
    assert "len(own_risk_reason) < 10" in router
    assert '"manager_at_own_risk_override"' in router
    assert '"approved_by_user_id": str(context.user.id)' in router
    assert '"approved_at": datetime.now(timezone.utc).isoformat()' in router


def test_quick_offer_edits_recheck_affordability() -> None:
    router = _read(ROOT / "routers/loan_offers.py")

    update_block = router.split("def update_offer(", 1)[1].split("@router.post", 1)[0]
    assert "_quick_affordability_for_terms(" in update_block
    assert "approve_at_own_risk" in update_block
    assert '"quick_affordability"' in update_block


def test_quick_offer_acceptance_requires_recorded_affordability_decision() -> None:
    service = _read(ROOT / "services/loan_service.py")

    accept_block = service.split("def accept_offer(", 1)[1].split("def _cash_reference", 1)[0]
    assert '"quick_affordability"' in accept_block
    assert "The lender must refresh this quick-loan offer" in accept_block
    assert "failed affordability and has no authorized at-risk approval" in accept_block


def test_marketplace_ui_shows_loanable_or_at_risk_choice() -> None:
    page = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/marketplace/_components/marketplace-request-dialog.tsx"
    )

    assert "Affordability decision" in page
    assert "LOANABLE" in page
    assert "NOT LOANABLE" in page
    assert "Approve at own risk" in page
    assert "This is an explicit management exception." in page
    assert "previewQuickLoanAffordability" in page
    assert "approve_at_own_risk" in page
    assert "own_risk_reason" in page
