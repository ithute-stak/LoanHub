"""Owner top-up decision centre must navigate to the direct top-up page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"
DECISION = (ROOT / "app/(dashboard)/company/origination/decision-centre/[applicationId]/page.tsx").read_text()
TOPUP = (ROOT / "app/(dashboard)/company/loans/top-up/page.tsx").read_text()
DIALOG = (ROOT / "components/loans/compact-top-up-dialog.tsx").read_text()
WIZARD = (ROOT / "app/(dashboard)/company/origination/new/page.tsx").read_text()


def test_decision_centre_directs_topups_to_separate_screen():
    assert 'application.application_type === "top_up" ? `/company/loans/top-up?application=' in DECISION
    assert '<Link href={`/company/loans/top-up?application=' in DECISION
    assert "Open direct top-up" in DECISION
    assert 'Review and decide top-up' in DECISION
    assert 'Open approved loan for contract &amp; disbursement' in DECISION
    assert 'do not pay out directly from this application screen' in DECISION


def test_method_aware_settlement_quote_is_visible_before_submission():
    assert '/top-up-settlement-preview' in DIALOG
    assert '/top-up-calculation-preview' in DIALOG
    assert 'Verified settlement quote' in TOPUP
    assert 'application.top_up_settlement_amount' in TOPUP
    assert 'settlement quote plus additional cash' in TOPUP
    assert 'Use saved records & review top-up' not in WIZARD
