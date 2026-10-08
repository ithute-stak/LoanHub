from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas" / "page.tsx"
OPERATIONS = ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "cdas" / "operations" / "page.tsx"


def test_read_actions_open_operator_feedback_modal() -> None:
    source = WORKSPACE.read_text(encoding="utf-8")

    assert "const [readFeedback, setReadFeedback]" in source
    assert '<Dialog open={readFeedback !== null}' in source
    assert "All third-party deductions" in source
    assert "Own deductions by status" in source
    assert "Active / approved deduction" in source
    assert "Affordability result" in source
    assert "Employee verified" in source
    assert "<DialogFooter showCloseButton />" in source


def test_main_cdas_workspace_exposes_full_deduction_lifecycle() -> None:
    source = WORKSPACE.read_text(encoding="utf-8")

    for label in (
        "Add deduction",
        "Review deduction",
        "Approve deduction",
        "Modify active deduction",
        "Settle deduction",
        "Reconcile / manage",
    ):
        assert label in source

    assert "/company/cdas/operations?action=register#lifecycle" in source
    assert "/company/cdas/operations?action=review#lifecycle" in source
    assert "/company/cdas/operations?action=approve#lifecycle" in source
    assert "/company/cdas/operations?action=modify#modify-active" in source
    assert "/company/cdas/operations?action=settle#settle" in source


def test_operations_screen_honours_deep_linked_action_without_effect_remount() -> None:
    source = OPERATIONS.read_text(encoding="utf-8")

    assert 'const requestedAction = searchParams.get("action") || "";' in source
    assert 'requestedAction === "review"' in source
    assert 'requestedAction === "approve"' in source
    assert 'id="lifecycle"' in source
    assert 'id="modify-active"' in source
    assert 'id="settle"' in source
    assert "useEffect" not in source
