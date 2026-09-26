from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal

from services.credit_committee_service import _vote_summary_from_rows


ROOT = Path(__file__).resolve().parents[2]


def _case(required_votes: int = 2, threshold: str = "66.667"):
    return SimpleNamespace(
        required_votes=required_votes,
        approval_threshold_percent=Decimal(threshold),
    )


def _vote(decision: str):
    return SimpleNamespace(decision=decision)


def test_committee_outcome_requires_quorum_before_any_final_result():
    result = _vote_summary_from_rows(_case(), [_vote("approve")])
    assert result["quorum_met"] is False
    assert result["computed_outcome"] is None


def test_committee_threshold_and_conditions_drive_computed_outcome():
    approved = _vote_summary_from_rows(_case(), [_vote("approve"), _vote("approve")])
    assert approved["quorum_met"] is True
    assert approved["computed_outcome"] == "approved"
    assert approved["approval_ratio_percent"] == 100.0

    conditional = _vote_summary_from_rows(
        _case(required_votes=3, threshold="66.667"),
        [_vote("approve"), _vote("approve_with_conditions"), _vote("reject")],
    )
    assert conditional["quorum_met"] is True
    assert conditional["computed_outcome"] == "conditionally_approved"

    rejected = _vote_summary_from_rows(
        _case(required_votes=3, threshold="75"),
        [_vote("approve"), _vote("approve"), _vote("reject")],
    )
    assert rejected["computed_outcome"] == "rejected"


def test_migration_preserves_historical_applications_and_governs_new_ones():
    migration = (ROOT / "backend" / "alembic" / "versions" / "h2n3q4s5t601_credit_committee_underwriting.py").read_text(encoding="utf-8")
    model = (ROOT / "backend" / "database" / "models" / "professional_lending.py").read_text(encoding="utf-8")

    assert 'down_revision = "g1m2p3r4s502"' in migration
    assert "UPDATE direct_loan_applications SET credit_committee_required = false" in migration
    assert "server_default=sa.true()" in migration
    assert "credit_committee_required = Column(Boolean, nullable=False, default=True, index=True)" in model


def test_committee_models_preserve_memo_votes_conditions_and_event_history():
    source = (ROOT / "backend" / "database" / "models" / "credit_committee.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "h2n3q4s5t601_credit_committee_underwriting.py").read_text(encoding="utf-8")

    for table in (
        "credit_committee_cases",
        "underwriting_assessments",
        "credit_committee_votes",
        "credit_committee_conditions",
        "credit_committee_events",
    ):
        assert table in source
        assert table in migration
    assert "uq_underwriting_assessment_case_revision" in source
    assert "uq_credit_committee_vote_case_user" in source
    assert 'maker_checker_required = Column(Boolean, nullable=False, default=True)' in source


def test_automated_credit_decision_is_evidence_not_committee_finalization():
    service = (ROOT / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")

    assert '"rules_engine": {' in service
    assert '"decision": rules_decision.decision if rules_decision else None' in service
    assert 'case.status = "committee_review"' in service
    assert "_vote_summary_from_rows" in service
    assert 'case.final_decision = decision' in service
    assert 'decision = "decline" if decline else "refer" if refer else "approve"' not in service


def test_maker_checker_quorum_and_override_controls_are_enforced():
    service = (ROOT / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "credit_committee.py").read_text(encoding="utf-8")

    assert "Maker-checker control prevents the underwriting analyst from voting on the same case" in service
    assert "Committee quorum is not met" in service
    assert "Only company management may override the computed committee outcome" in service
    assert "A documented override reason is required" in service
    assert "allow_override=context.role in COMPANY_MANAGEMENT_ROLES" in router


def test_credit_conditions_block_approval_and_disbursement_at_transaction_boundary():
    integrity = (ROOT / "backend" / "core" / "credit_committee_integrity.py").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert '_open_condition_count(session, case.id, {"pre_contract"})' in integrity
    assert '_open_condition_count(session, case.id, {"pre_contract", "pre_disbursement"})' in integrity
    assert "Credit Committee approval is required before this application can be approved" in integrity
    assert "Credit Committee pre-disbursement condition(s) remain unresolved" in integrity
    assert 'event.listen(Session, "before_flush", _before_flush)' in integrity
    assert "install_credit_committee_integrity()" in main


def test_credit_committee_api_and_ui_cover_full_human_decision_cycle():
    router = (ROOT / "backend" / "routers" / "credit_committee.py").read_text(encoding="utf-8")
    api_router = (ROOT / "backend" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "credit-committee" / "page.tsx").read_text(encoding="utf-8")
    case_page = (ROOT / "frontend" / "app" / "(dashboard)" / "company" / "credit-committee" / "cases" / "[caseId]" / "page.tsx").read_text(encoding="utf-8")
    api_client = (ROOT / "frontend" / "api" / "creditCommittee.ts").read_text(encoding="utf-8")

    assert '@router.get("/dashboard")' in router
    assert '@router.post("/intake/{application_id}"' in router
    assert '@router.post("/cases/{case_id}/assessment"' in router
    assert '@router.put("/cases/{case_id}/vote")' in router
    assert '@router.post("/cases/{case_id}/finalize")' in router
    assert '@router.patch("/cases/{case_id}/conditions/{condition_id}")' in router
    assert '@router.get("/cases/{case_id}/credit-memo.pdf")' in router
    assert "credit_committee.router" in api_router
    assert "Credit Committee & Underwriting" in dashboard
    assert "Analyst underwriting credit memo" in case_page
    assert "Committee voting" in case_page
    assert "Decision conditions" in case_page
    assert "downloadCreditMemo" in api_client
