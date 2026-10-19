"""Top-up credit bureau remains optional while normal origination rules remain enforced."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "services/lending_integration_service.py").read_text()


def test_topup_optional_bureau_readiness():
    for name in ("bureau_required_affordability", "bureau_required_approval"):
        section = SOURCE.split(f"    {name} = bool(", 1)[1].split("    )", 1)[0]
        assert 'application.application_type != "top_up"' in section
        assert "bureau_enabled" in section
    assert 'if bureau_enabled:' in SOURCE
    assert 'elif bureau_enabled and not bureau_fresh:' in SOURCE
    assert 'if bureau_enabled and not bureau_platform_ready:' in SOURCE


def test_core_affordability_remains_required():
    assert '"affordability_not_positive"' in SOURCE
    assert '"top_up_affordability_outdated"' in SOURCE
    assert '"ready_for_approval"' in SOURCE


# Regression: the origination affordability calculator is a separate gate from
# integration readiness. Keep both aligned for top-up applications.
ORIGINATION_SOURCE = (Path(__file__).resolve().parents[1] / "services/origination_service.py").read_text()


def test_topup_affordability_does_not_require_active_experian():
    assert 'is_top_up = application.application_type == "top_up"' in ORIGINATION_SOURCE
    assert 'if not is_top_up and (not bureau_policy_row or not bureau_policy_row.is_enabled):' in ORIGINATION_SOURCE
    assert 'if bureau_policy_row and bureau_policy_row.is_enabled:' in ORIGINATION_SOURCE
    assert 'if not is_top_up:' in ORIGINATION_SOURCE
    assert 'if not latest_bureau and not is_top_up:' in ORIGINATION_SOURCE
    assert '"Credit-bureau integration must be enabled before affordability can be calculated."' in ORIGINATION_SOURCE
    assert '"A fresh credit-bureau report is required before affordability can be calculated."' in ORIGINATION_SOURCE


def test_topup_affordability_keeps_income_and_cdas_checks():
    assert '"income_below_minimum"' in ORIGINATION_SOURCE
    assert '"kyc_incomplete"' in ORIGINATION_SOURCE
    assert 'live_cdas_affordability' in ORIGINATION_SOURCE


def test_enabled_bureau_contributes_evidence_but_is_optional_for_topups():
    assert 'if bureau_fresh and latest_bureau:' in SOURCE
    assert 'if bureau_fresh:' in ORIGINATION_SOURCE
    assert 'bureau_monthly_commitments = money(latest_bureau.monthly_obligations if latest_bureau else 0)' in ORIGINATION_SOURCE
    assert 'if not latest_bureau and not is_top_up:' in ORIGINATION_SOURCE
