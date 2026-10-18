"""Owner top-up fast track retains underwriting and signing controls."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WIZARD = (ROOT / "frontend/app/(dashboard)/company/origination/new/page.tsx").read_text()


def test_fast_track_skips_form_entry_not_actual_assessment():
    assert "Skip forms & offer top-up" in WIZARD
    assert 'activeRole === "company_owner"' in WIZARD
    section = WIZARD.split("async function skipToTopUpOffer()", 1)[1].split("async function submitApplication()", 1)[0]
    assert "await ensureApplication()" in section
    assert "originationApi.assess(current.id" in section
    assert "proposed_principal: Number(current.requested_amount)" in section
    assert "originationApi.submit(current.id)" in section
    assert "setStep(6)" in section
    assert "originationApi.approve" not in section
    assert "disburse" not in section
