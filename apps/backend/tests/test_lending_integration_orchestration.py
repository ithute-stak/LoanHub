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
    assert "score_below_decline_threshold" in service
    assert "defaults_blocked" in service
    assert "identity_match_required" in service
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
