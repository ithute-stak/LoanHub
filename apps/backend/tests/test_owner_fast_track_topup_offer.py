"""Owner top-up direct-entry flow retains management and settlement protections."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WIZARD = (ROOT / "frontend/app/(dashboard)/company/origination/new/page.tsx").read_text()
DIRECT = (ROOT / "frontend/app/(dashboard)/company/loans/top-up/page.tsx").read_text()
DECISION = (ROOT / "frontend/app/(dashboard)/company/origination/decision-centre/[applicationId]/page.tsx").read_text()


def test_owner_fast_track_uses_direct_topup_not_origination_wizard():
    assert 'Open direct top-up' in DECISION
    assert '/company/loans/top-up?application=' in DECISION
    assert 'Skip forms &amp; offer top-up' not in DECISION
    assert '>Top-up existing loan</p>' not in WIZARD
    assert 'Use saved records & review top-up' not in WIZARD


def test_topup_creates_draft_then_requests_management_approval():
    assert "originationApi.submit(application.id)" in DIRECT
    assert "originationApi.approveTopUpException(application.id" in DIRECT
    assert '"draft"' in DIRECT
    assert 'disburseLoan(' not in DIRECT
    assert 'No affordability assessment' not in DIRECT or 'no credit origination wizard or affordability assessment' in DIRECT
