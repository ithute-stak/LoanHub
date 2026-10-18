"""Owner top-up decision centre should only show stage-appropriate actions."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/company/origination/decision-centre/[applicationId]/page.tsx").read_text()


def test_owner_uses_draft_fast_track_and_waits_for_authorized_approval():
    assert 'application.status === "draft"' in SOURCE
    assert 'Skip forms &amp; offer top-up' in SOURCE
    assert '["submitted", "under_review"].includes(application.status)' in SOURCE
    assert 'Review and decide top-up' in SOURCE
    assert 'application.status === "approved" && application.loan_id' in SOURCE
    assert 'Open approved loan for contract &amp; disbursement' in SOURCE
    assert 'do not pay out directly from this application screen' in SOURCE
