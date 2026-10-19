"""Top-up credit bureau remains optional while normal origination rules remain enforced."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "services/lending_integration_service.py").read_text()


def test_topup_optional_bureau_readiness():
    for name in ("bureau_required_affordability", "bureau_required_approval"):
        section = SOURCE.split(f"    {name} = bool(", 1)[1].split("    )", 1)[0]
        assert 'application.application_type != "top_up"' in section
        assert "bureau_enabled" in section
    assert 'if bureau_enabled and application.application_type != "top_up":' in SOURCE
    assert 'elif bureau_enabled and application.application_type != "top_up" and not bureau_fresh:' in SOURCE
    assert 'if bureau_enabled and application.application_type != "top_up" and not bureau_platform_ready:' in SOURCE


def test_core_affordability_remains_required():
    assert '"affordability_not_positive"' in SOURCE
    assert '"top_up_affordability_outdated"' in SOURCE
    assert '"ready_for_approval"' in SOURCE
