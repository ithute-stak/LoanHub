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


def test_credit_committee_is_advisory_at_transaction_boundary():
    integrity = (ROOT / "backend" / "core" / "credit_committee_integrity.py").read_text(encoding="utf-8")
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert "optional governance workflow" in integrity
    assert "universal ORM transaction gate" in integrity
    assert "Credit Committee approval is required before this application can be approved" not in integrity
    assert "Credit Committee clearance is missing for this loan" not in integrity
    assert 'event.listen(Session, "before_flush", _before_flush)' not in integrity
    assert 'event.listen(CreditCommitteeCondition, "before_insert", _normalize_condition_date)' in integrity
    assert 'event.listen(CreditCommitteeCondition, "before_update", _normalize_condition_date)' in integrity
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



def test_committee_uses_same_application_scoped_external_evidence_as_decision_centre():
    service = (ROOT / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")
    external = (ROOT / "backend" / "services" / "external_underwriting_evidence_service.py").read_text(encoding="utf-8")

    assert "company_experian_policy(" in service
    assert "latest_fresh_experian_enquiry(" in service
    assert "application_id=application.id" in service
    assert 'environment=str(bureau_policy.get("environment") or "sandbox")' in service
    assert "external_evidence_snapshot(" in service
    assert '"external_underwriting_evidence": external_evidence' in service
    assert "available_deduction_capacity" in external
    assert "cdas_existing_deductions_are_capacity_only" in external



def test_committee_approval_revalidates_current_integrations_and_final_evidence():
    service = (ROOT / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")

    assert "final_integration_readiness = assert_application_integration_readiness_for_approval(" in service
    assert "final_evidence_snapshot = build_evidence_snapshot(db, application)" in service
    assert 'decision in {"approved", "conditionally_approved"}' in service
    assert '"final_integration_readiness": final_integration_readiness' in service
    assert '"final_evidence_snapshot": final_evidence_snapshot' in service
    assert '"final_evidence_captured_at": (' in service


def test_committee_revalidation_uses_assessed_installment():
    service = (ROOT / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")

    assert "proposed_installment=(" in service
    assert "Decimal(assessment.proposed_installment)" in service



def test_committee_uses_same_application_scoped_external_evidence_as_decision_centre():
    service = (ROOT / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")
    external = (ROOT / "backend" / "services" / "external_underwriting_evidence_service.py").read_text(encoding="utf-8")

    assert "company_experian_policy(" in service
    assert "latest_fresh_experian_enquiry(" in service
    assert "application_id=application.id" in service
    assert 'environment=str(bureau_policy.get("environment") or "sandbox")' in service
    assert "external_evidence_snapshot(" in service
    assert '"external_underwriting_evidence": external_evidence' in service
    assert "available_deduction_capacity" in external
    assert "cdas_existing_deductions_are_capacity_only" in external


def test_committee_deal_structuring_is_evidence_only_and_survives_to_final_snapshot():
    root = Path(__file__).resolve().parents[2]
    router = (root / "backend" / "routers" / "credit_committee.py").read_text(encoding="utf-8")
    service = (root / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")
    api = (root / "frontend" / "api" / "creditCommittee.ts").read_text(encoding="utf-8")
    page = (root / "frontend" / "app" / "(dashboard)" / "company" / "credit-committee" / "cases" / "[caseId]" / "page.tsx").read_text(encoding="utf-8")

    assert '@router.post("/cases/{case_id}/deal-structures")' in router
    assert '@router.post("/cases/{case_id}/deal-structures/select")' in router
    assert '"deal_structures_generated"' in router
    assert '"deal_structure_selected"' in router
    assert "A non-viable structure cannot be selected" in router
    assert "does not approve credit, alter the application or bypass voting" in router

    assert 'snapshot["selected_deal_structure"] = selected_deal_structure' in service
    assert '"selected_deal_structure": (case.evidence_snapshot or {}).get("selected_deal_structure")' in service

    assert "generateCommitteeDealStructures" in api
    assert "selectCommitteeDealStructure" in api
    assert "Deal Structuring Intelligence" in page
    assert "Generate viable structures" in page
    assert "Selected committee structure" in page
    assert "copies into the analyst proposal fields" not in page


def test_post_approval_disbursement_integrity_guard_blocks_material_drift_and_is_previewable():
    root = Path(__file__).resolve().parents[2]
    committee = (root / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")
    loan_service = (root / "backend" / "services" / "loan_service.py").read_text(encoding="utf-8")
    loans_router = (root / "backend" / "routers" / "loans.py").read_text(encoding="utf-8")
    loans_api = (root / "frontend" / "api" / "loans.ts").read_text(encoding="utf-8")
    loans_page = (root / "frontend" / "app" / "(dashboard)" / "company" / "loans" / "page.tsx").read_text(encoding="utf-8")

    assert "def _post_approval_deal_integrity(" in committee
    assert "def preview_loan_disbursement_integrity(" in committee
    assert "loan principal differs from the committee-selected structure" in committee
    assert "loan term differs from the committee-selected structure" in committee
    assert "below the committee-selected minimum viable pricing floor" in committee
    assert "contract principal differs from the loan" in committee
    assert "loan installment exceeds the current maximum affordable installment" in committee
    assert "post-disbursement 30-day liquidity falls below the approved minimum liquidity buffer" in committee
    assert '"removed_new_loan_collection_credit"' in committee
    assert '"disbursement_integrity_verified"' in committee
    assert "actor_user_id=actor_user_id" in committee

    assert "owner_override_verified=owner_override_verified" in loan_service
    assert "assert_disbursement_governance_ready(" in loan_service

    assert '@router.get("/{loan_id}/disbursement-integrity")' in loans_router
    assert "This preview is read-only" in loans_router

    assert "DisbursementIntegrityPreview" in loans_api
    assert "getDisbursementIntegrityPreview" in loans_api

    assert "Post-approval integrity verified" in loans_page
    assert "Disbursement blocked by integrity guard" in loans_page
    assert "removed_new_loan_collection_credit" not in loans_page
    assert "ownerOverrideEligible" in loans_page
    assert "ownerOverrideReady" in loans_page
    assert "Controlled Owner Override" in loans_page
    assert "owner_override_confirmed: ownerOverrideReady" in loans_page


def test_company_owner_cash_override_is_strictly_scoped_and_audited():
    root = Path(__file__).resolve().parents[2]
    committee = (root / "backend" / "services" / "credit_committee_service.py").read_text(encoding="utf-8")
    loan_service = (root / "backend" / "services" / "loan_service.py").read_text(encoding="utf-8")
    loans_router = (root / "backend" / "routers" / "loans.py").read_text(encoding="utf-8")
    cash_schema = (root / "backend" / "database" / "schemas" / "cash.py").read_text(encoding="utf-8")
    audit_integrity = (root / "backend" / "core" / "audit_integrity.py").read_text(encoding="utf-8")
    loans_page = (root / "frontend" / "app" / "(dashboard)" / "company" / "loans" / "page.tsx").read_text(encoding="utf-8")

    assert "owner_override_verified: bool = False" in committee
    assert "Owner override may bypass only Credit Committee clearance/condition blockers" in committee
    assert '"Credit Committee clearance is missing for this loan"' in committee
    assert '"Credit Committee pre-contract/pre-disbursement conditions remain open"' in committee

    assert "payment_method == PaymentMethod.CASH" in loan_service
    assert '"owner_committee_override": owner_override_verified' in loan_service

    assert "context.role != UserRole.COMPANY_OWNER" in loans_router
    assert "payload.payment_method != PaymentMethod.CASH" in loans_router
    assert "Enable MFA on the company-owner account before using the disbursement override" in loans_router
    assert "verify_password(" in loans_router
    assert "verify_second_factor(" in loans_router
    assert 'action="loan.disbursement_owner_committee_override"' in loans_router
    assert 'severity="critical"' in loans_router

    assert "owner_override_confirmed: bool = False" in cash_schema
    assert "owner_override_reason" in cash_schema
    assert "owner_reauth_otp" in cash_schema
    assert "owner_reauth_recovery_code" in cash_schema

    assert "Sealed audit events are immutable" in audit_integrity
    assert "Controlled Owner Override" in loans_page
    assert "MFA must already be enabled on the owner account" in loans_page
