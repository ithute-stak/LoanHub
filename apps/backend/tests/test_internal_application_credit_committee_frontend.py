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


def test_internal_application_queue_has_committee_actions() -> None:
    text = source()
    assert 'Send to Committee' in text
    assert 'View Committee Case' in text
    assert '/company/credit-committee/cases/' in text


def test_final_loan_approval_is_visibly_gated_by_committee() -> None:
    text = source()
    assert 'selectedCommitteeApproved' in text
    assert '!selectedCommitteeApproved || !selectedProduct || !calculation || calculating' in text
    assert 'Credit Committee approval is required first' in text
    assert 'Final loan approval remains locked until Credit Committee approval' in text


def test_conditional_approval_requires_pre_contract_conditions_resolved() -> None:
    text = source()
    assert 'condition.condition_type === "pre_contract"' in text
    assert '["satisfied", "waived"].includes(condition.status)' in text
