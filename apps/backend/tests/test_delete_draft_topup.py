from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = (ROOT / "routers/origination.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/origination/page.tsx").read_text()


def test_delete_draft_topup_is_scoped_and_soft_deleted():
    section = ROUTER.split("def delete_draft_top_up(", 1)[1].split("@router.", 1)[0]
    assert "UserRole.COMPANY_OWNER" in section
    assert "UserRole.BRANCH_MANAGER" in section
    assert "_application(db, context=context, application_id=application_id, lock=True)" in section
    assert 'application.application_type != "top_up" or application.status != "draft"' in section
    assert "application.loan_id is not None" in section
    assert 'application.status = "cancelled"' in section
    assert "db.delete(application)" not in section


def test_cancelled_draft_removed_from_listing_and_duplicate_guard():
    list_section = ROUTER.split("def list_applications(", 1)[1].split("@router.", 1)[0]
    assert 'DirectLoanApplication.status != "cancelled"' in list_section
    source = (ROOT / "services/origination_service.py").read_text()
    assert 'OPEN_APPLICATION_STATUSES = {"draft", "submitted", "under_review"}' in source


def test_draft_topup_delete_requires_confirmed_user_action():
    assert 'application.status === "draft"' in UI
    assert 'setDeleteTopUp(application)' in UI
    assert "originationApi.deleteDraftTopUp(deleteTopUp.id)" in UI
    assert "Delete draft top-up" in UI


def test_owner_threshold_exception_does_not_block_draft_deletion():
    section = ROUTER.split("def delete_draft_top_up(", 1)[1].split("@router.", 1)[0]
    assert "application.top_up_exception_approved" not in section
    assert 'application.status != "draft"' in section
    assert "application.submitted_at is not None" in section
    assert "application.approved_at is not None" in section
    assert "application.loan_id is not None" in section
    assert 'application.status = "cancelled"' in section
