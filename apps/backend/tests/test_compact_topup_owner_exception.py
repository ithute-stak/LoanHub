from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIALOG = ROOT / "frontend/components/loans/compact-top-up-dialog.tsx"
ROUTER = ROOT / "backend/routers/origination.py"


def test_compact_dialog_allows_reasoned_owner_exception_only():
    source = DIALOG.read_text()
    assert "eligibility?.requires_owner_exception" in source
    assert "exceptionReason.trim().length >= 10" in source
    assert "top_up_exception_reason: ownerException ? exceptionReason.trim() : null" in source
    assert "Request owner exception" in source
    assert "eligibility?.eligible || (ownerException" in source


def test_owner_exception_decision_remains_owner_only():
    source = ROUTER.read_text()
    endpoint = source.split("def approve_top_up_exception(", 1)[1].split("@router.", 1)[0]
    assert "require_tenant_roles(context, {UserRole.COMPANY_OWNER})" in endpoint
    assert "policy.top_up_owner_exception_enabled" in endpoint
    assert "application.top_up_exception_approved = True" in endpoint


def test_compact_creation_remains_non_approving():
    source = ROUTER.read_text().split("def create_compact_top_up(", 1)[1].split("@router.", 1)[0]
    assert "create_application(" in source
    assert "approve_top_up_exception" not in source
