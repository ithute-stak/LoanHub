"""Prevent reintroduction of retired affordability into active LoanHub workflows."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "frontend"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_live_affordability_routes_or_submission_gate():
    router = read(ROOT / "routers/origination.py")
    assert '@router.post("/applications/{application_id}/assess")' not in router
    assert '@router.post("/assessments/{assessment_id}/override")' not in router
    assert "A positive affordability assessment is required" not in router
    payload = router.split("def _application_payload(", 1)[1].split("def _contract_payload(", 1)[0]
    assert 'data["affordability_decision"]' not in payload
    workspace = router.split("def application_workspace(", 1)[1].split("def ", 1)[0]
    assert '"assessments":' not in workspace


def test_no_affordability_approval_readiness_gate():
    readiness = read(ROOT / "services/lending_integration_service.py")
    assert "AffordabilityAssessment" not in readiness
    for code in ("affordability_not_positive", "top_up_affordability_outdated", "affordability_stale_after_bureau"):
        assert code not in readiness
    assert 'cdas_capacity["blockers"]' not in readiness
    assert 'bool(cdas_capacity["capacity_sufficient"])' not in readiness
    assert '"payroll_profile_not_verified"' in readiness


def test_committee_no_longer_exports_current_affordability_evidence():
    service = read(ROOT / "services/credit_committee_service.py")
    report = read(ROOT / "services/credit_committee_report_service.py")
    active_snapshot = service.split("def build_evidence_snapshot(", 1)[1].split("def ", 1)[0]
    assert '"affordability":' not in active_snapshot
    assert "_latest_affordability(" not in service
    assert "Application and affordability evidence" not in report
    assert "Affordability result" not in report


def test_user_facing_origination_and_topup_have_no_affordability_screen():
    wizard = read(WEB / "app/(dashboard)/company/origination/new/page.tsx")
    dashboard = read(WEB / "app/(dashboard)/company/origination/page.tsx")
    topup = read(WEB / "components/loans/compact-top-up-dialog.tsx")
    committee = read(WEB / "app/(dashboard)/company/credit-committee/cases/[caseId]/page.tsx")
    for ui in (wizard, dashboard, committee):
        assert "Affordability decision" not in ui
        assert 'label="Affordability"' not in ui
    assert "No affordability assessment is required" in topup
