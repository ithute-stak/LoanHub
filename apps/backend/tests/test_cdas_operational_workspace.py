from __future__ import annotations

from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parents[1] / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cdas_operations_feed_is_loanhub_first() -> None:
    router = _read(BACKEND / "routers/cdas_api.py")

    assert '@router.get("/loans/operations")' in router
    assert '"next_action": next_action' in router
    assert '"autopilot_pending": plan.get("autopilot_pending")' in router
    assert '"autopilot_last_result": plan.get("autopilot_last_result")' in router
    assert '"autopilot_topup_opportunity": plan.get("autopilot_topup_opportunity")' in router
    assert 'next_action = "register"' in router
    assert 'next_action = "reconcile"' in router
    assert 'next_action = "manage"' in router


def test_linked_loan_can_reconcile_latest_unresolved_provider_operation() -> None:
    router = _read(BACKEND / "routers/cdas_api.py")

    assert '@router.post("/loans/{loan_id}/reconcile")' in router
    assert "CdasProviderOperation.state.in_(UNRESOLVED_OPERATION_STATES)" in router
    assert "await reconcile_provider_operation(" in router
    assert "state.requires_reconciliation = not matched" in router


def test_operator_workspace_supports_add_track_reconcile_and_manage() -> None:
    page = _read(FRONTEND / "app/(dashboard)/company/cdas/manage/page.tsx")

    assert '"/cdas/loans/operations"' in page
    assert "Add to CDAS" in page
    assert "Confirm and Add to CDAS" in page
    assert '"/register"' in page
    assert '"/reconcile"' in page
    assert "Review" in page
    assert "Approve" in page
    assert "Advanced controls" in page
    assert "autopilot_topup_opportunity" in page
    assert "autopilot_pending" in page


def test_cdas_home_routes_normal_staff_to_operator_workspace() -> None:
    page = _read(FRONTEND / "app/(dashboard)/company/cdas/page.tsx")

    assert 'href="/company/cdas/manage"' in page
    assert "Manage deductions" in page
    assert "Live operations + Autopilot" in page
    assert "Nothing on this page runs in the background" not in page


def test_advanced_controls_accept_selected_loan_deep_link() -> None:
    page = _read(FRONTEND / "app/(dashboard)/company/cdas/operations/page.tsx")

    assert "useEffect" in page
    assert 'new URLSearchParams(window.location.search).get("loan")' in page
    assert "setSelectedLoanId(loanId)" in page
