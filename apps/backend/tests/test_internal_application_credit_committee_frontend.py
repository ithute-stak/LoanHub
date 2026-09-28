from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "frontend" / "app" / "(dashboard)" / "company" / "marketplace" / "_components" / "internal-applications-workspace.tsx"


def source() -> str:
    return WORKSPACE.read_text(encoding="utf-8")


def test_internal_application_queue_surfaces_credit_committee_state() -> None:
    text = source()
    assert 'getCommitteeDashboard' in text
    assert 'intakeCommitteeApplication' in text
    assert '<TableHead>Credit Committee</TableHead>' in text
    assert 'Not submitted' in text
    assert 'Underwriting' in text
    assert 'Committee review' in text
    assert 'Awaiting conditions' in text
    assert 'Conditionally approved' in text
    assert 'Rejected' in text


def test_internal_application_queue_has_optional_committee_actions() -> None:
    text = source()
    assert 'Send to Committee' in text
    assert 'View Committee Case' in text
    assert '/company/credit-committee/cases/' in text
    assert 'Credit Committee review is optional' in text


def test_final_loan_approval_is_not_blocked_by_committee_state() -> None:
    text = source()
    assert 'if (!selected || !selectedProduct || !calculation) return;' in text
    assert 'disabled={!selectedProduct || !calculation || calculating}' in text
    assert '!selectedCommitteeApproved || !selectedProduct || !calculation || calculating' not in text
    assert 'Credit Committee approval is required first' not in text
    assert 'Final loan approval remains locked until Credit Committee approval' not in text


def test_committee_outcome_remains_visible_for_governance() -> None:
    text = source()
    assert 'selectedCommitteeApproved' in text
    assert 'The committee recorded a rejection' in text
    assert 'record the approval rationale if proceeding' in text
