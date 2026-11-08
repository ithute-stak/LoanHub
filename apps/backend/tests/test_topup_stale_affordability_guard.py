"""Affordability is not an active precondition for top-up approval."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "services/lending_integration_service.py").read_text()


def test_topup_does_not_require_a_fresh_affordability_assessment():
    section = SOURCE.split("def application_integration_readiness(", 1)[1].split(
        "def assert_application_integration_readiness_for_approval(", 1
    )[0]
    assert '"top_up_affordability_outdated"' not in section
    assert '"affordability_stale_after_bureau"' not in section
    assert '"affordability_not_positive"' not in section
    assert "cdas_deduction_capacity(" in section
