"""Top-up flows must not depend on the retired affordability module."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS = (ROOT / "services/lending_integration_service.py").read_text(encoding="utf-8")
ORIGINATION = (ROOT / "routers/origination.py").read_text(encoding="utf-8")
COMPACT = (ROOT.parent / "frontend/components/loans/compact-top-up-dialog.tsx").read_text(encoding="utf-8")


def test_topup_has_no_legacy_affordability_submission_or_approval_gates():
    section = READINESS.split("def application_integration_readiness(", 1)[1].split(
        "def assert_application_integration_readiness_for_approval(", 1
    )[0]
    for old_code in ("top_up_affordability_outdated", "affordability_stale_after_bureau", "affordability_not_positive"):
        assert old_code not in section
    submit = ORIGINATION.split("def submit_application(", 1)[1].split("@router.post(", 1)[0]
    assert "A positive affordability assessment is required" not in submit


def test_all_loans_skip_retired_capacity_gate_but_keep_cdas_identity():
    assert "enforce_cdas_capacity_in_readiness" not in READINESS
    assert 'cdas_verified and not cdas_capacity["capacity_sufficient"]' not in READINESS
    assert 'cdas_capacity["blockers"]' not in READINESS
    assert '"payroll_profile_not_verified"' in READINESS
    assert "cdas_provider_configured" in READINESS


def test_topup_preview_and_compact_dialog_do_not_request_affordability():
    assert '"requires_credit_assessment": False' in ORIGINATION
    assert "No affordability assessment is required." in COMPACT
    assert "validate current affordability" not in COMPACT


def test_topup_still_uses_ledger_settlement_and_management_decision():
    assert "preview_top_up_settlement(" in ORIGINATION
    assert "replacement_principal(" in ORIGINATION
    assert "top_up_eligibility(" in ORIGINATION
    assert 'def approve_top_up_exception(' in ORIGINATION
