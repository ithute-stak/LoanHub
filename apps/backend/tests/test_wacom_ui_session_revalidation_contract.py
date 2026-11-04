"""Contract UI must never treat advisory pad-session status as capture authorization."""
from pathlib import Path


def test_operator_ui_polls_authenticated_session_status_and_fails_closed():
    root = Path(__file__).resolve().parents[3]
    ui = (root / "apps/frontend/components/contracts/contract-pad-preflight.tsx").read_text()
    assert "window.setInterval" in ui
    assert "window.clearInterval" in ui
    assert "5000" in ui
    assert "sessionStatusError" in ui
    assert "workstation_capture_authorized !== false" in ui
    assert "data.capture_enabled !== false" in ui
    assert "preview_eligible" in ui
    assert "sessionStatus?.preview_eligible" in ui
    assert "onCapture=" not in ui
    assert "Hardware signing remains disabled" in ui


def test_existing_signing_endpoints_still_refuse_hardware_capture():
    root = Path(__file__).resolve().parents[3]
    api = (root / "apps/backend/routers/contract_email_otp.py").read_text()
    assert '"capture_enabled": False' in api
    assert '"workstation_capture_authorized": False' in api
    assert "current_pad_preview_eligibility" in api
