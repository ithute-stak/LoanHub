"""Approval must not reuse a positive assessment for different top-up installments."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "services/lending_integration_service.py").read_text()


def test_stale_topup_affordability_blocks_approval():
    section = SOURCE.split("def application_integration_readiness(", 1)[1].split(
        "def assert_application_integration_readiness_for_approval(", 1
    )[0]
    assert 'application.application_type == "top_up"' in section
    assert 'abs(Decimal(assessment.proposed_installment) - Decimal(proposed_installment)) > Decimal("0.01")' in section
    assert '"top_up_affordability_outdated"' in section
    assert 'core_ready = False' in section
    assert 'Recalculate affordability before approval' in section
