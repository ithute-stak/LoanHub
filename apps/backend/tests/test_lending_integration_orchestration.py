from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_origination_workspace_exposes_one_cross_system_readiness_view() -> None:
    router = _read(ROOT / "routers/origination.py")
    service = _read(ROOT / "services/lending_integration_service.py")

    assert 'integration_readiness": application_integration_readiness(' in router
    assert '@router.get("/applications/{application_id}/integration-readiness")' in router
    assert "def application_integration_readiness(" in service
    assert '"core": {' in service
    assert '"bureau": {' in service
    assert '"cdas": {' in service
    assert '"ready_for_affordability": ready_for_affordability' in service
    assert '"ready_for_approval": ready_for_approval' in service


def test_approval_uses_unified_core_bureau_cdas_gate() -> None:
    router = _read(ROOT / "routers/professional_lending.py")
    service = _read(ROOT / "services/lending_integration_service.py")

    assert "assert_application_integration_readiness_for_approval(" in router
    external = _read(ROOT / "services/external_underwriting_evidence_service.py")
    assert "bureau_evidence(" in service
    assert "cdas_deduction_capacity(" in service
    assert "score_below_decline_threshold" in external
    assert "defaults_blocked" in external
    assert "judgments_blocked" in external
    assert "collections_blocked" in external
    assert "identity_match_required" in external
    assert "deduction_capacity_insufficient" in external
    assert "affordability_stale_after_bureau" in service
    assert "payroll_profile_not_verified" in service


def test_core_and_cdas_employee_identity_mismatch_is_visible() -> None:
    service = _read(ROOT / "services/lending_integration_service.py")
    origination_router = _read(ROOT / "routers/origination.py")

    assert "BorrowerEmploymentProfile" in service
    assert "employee_number_mismatch" in service
    assert "CDASPayrollProfile.verified.is_(True)" in origination_router
    assert "A verified CDAS payroll profile with an employee number is required" in origination_router


def test_origination_ui_shows_unified_readiness_and_deep_links_to_providers() -> None:
    page = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/new/page.tsx")
    bureau = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/experian/page.tsx")
    cdas = _read(FRONTEND_ROOT / "app/(dashboard)/company/cdas/page.tsx")

    assert "Core · Bureau · CDAS" in page
    assert "One readiness view shared by LoanHub approval, Experian and CDAS." in page
    assert "integrationReadiness?.blockers.map" in page
    assert "integrationReadiness?.warnings.map" in page
    assert "originationApi.getIntegrationReadiness" in page

    assert 'new URLSearchParams(window.location.search).get("application")' in bureau
    assert "apps.some((item) => item.id === requestedApplicationId)" in bureau

    assert 'new URLSearchParams(window.location.search).get("application")' in cdas
    assert "eligible.some((application) => application.id === requestedApplicationId)" in cdas
    assert "useEffect" not in cdas

def test_unified_decision_centre_surfaces_core_bureau_cdas_and_final_outcome() -> None:
    service = _read(ROOT / "services/lending_integration_service.py")
    page = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/origination/decision-centre/[applicationId]/page.tsx"
    )
    dashboard = _read(FRONTEND_ROOT / "app/(dashboard)/company/origination/page.tsx")
    manager = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/marketplace/_components/internal-applications-workspace.tsx"
    )

    assert '"final_decision": final_decision' in service
    assert 'final_decision = "loanable"' in service
    assert 'final_decision = "not_loanable"' in service
    assert 'final_decision = "action_required"' in service
    assert '"completed_at": latest_bureau.completed_at.isoformat()' in service

    assert "Unified Loan Decision Centre" in page
    assert "Core LoanHub" in page
    assert "Experian / Bureau" in page
    assert "CDAS" in page
    assert "Final decision" in page
    assert "LOANABLE" in page
    assert "NOT LOANABLE" in page
    assert "Approval blockers" in page
    assert "Decision evidence timeline" in page
    assert "/company/origination/experian?application=" in page
    assert "/company/cdas?application=" in page
    assert "/company/marketplace?workspace=applications&application=" in page

    assert "/company/origination/decision-centre/${application.id}" in dashboard
    assert 'new URLSearchParams(window.location.search).get("application")' in manager
    assert "openApplication(requested)" in manager



def test_unified_decision_centre_shows_full_external_evidence() -> None:
    service = _read(ROOT / "services/lending_integration_service.py")
    page = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/origination/decision-centre/[applicationId]/page.tsx"
    )

    assert '"judgments_count": bureau_snapshot["judgments_count"]' in service
    assert '"collections_count": bureau_snapshot["collections_count"]' in service
    assert '"available_deduction_capacity": float(cdas_capacity["available_deduction_capacity"])' in service
    assert '"capacity_sufficient": bool(cdas_capacity["capacity_sufficient"])' in service
    assert "Judgments" in page
    assert "Collections" in page
    assert "Available deduction capacity" in page
    assert "Proposed installment" in page



def test_direct_approval_revalidates_against_final_calculated_installment() -> None:
    router = _read(ROOT / "routers/professional_lending.py")
    service = _read(ROOT / "services/lending_integration_service.py")

    calculate_pos = router.index("monthly, total, calculation_breakdown = calculate_loan_terms(")
    readiness_pos = router.index("assert_application_integration_readiness_for_approval(")
    assert calculate_pos < readiness_pos
    approval_block = router[readiness_pos:readiness_pos + 1200]
    assert "amount=Decimal(payload.approved_amount)" in approval_block
    assert "product_id=product_id" in approval_block
    assert "proposed_installment=monthly" in approval_block
    assert "proposed_installment: Decimal | None = None" in service
    assert "proposed_installment if proposed_installment is not None" in service
