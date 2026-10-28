"""Regression checks for authenticated, transfer-bound checker decisions."""
from pathlib import Path

ROUTER=(Path(__file__).resolve().parents[1]/"routers/loans.py").read_text()
SERVICE=(Path(__file__).resolve().parents[1]/"services/rollover_checker_decision.py").read_text()


def test_checker_identity_comes_from_authenticated_tenant():
    endpoint=ROUTER.split('def submit_rollover_checker_decision(',1)[1].split('\n\n\n',1)[0]
    assert 'checker_user_id=context.user.id' in endpoint
    assert 'company_id=context.company_id' in endpoint
    assert 'require_tenant_roles(context' in endpoint
    assert 'posting_enabled' in SERVICE


def test_maker_anchored_to_prior_transfer_evidence():
    assert 'maker_id = transfer.posted_by_user_id' in SERVICE
    assert 'verify_rollover_checker_identity(' in SERVICE
    assert 'with_for_update()' in SERVICE
    assert 'Decision already recorded for this transfer' in SERVICE
    assert 'except IntegrityError:' in SERVICE
    assert 'db.rollback()' in SERVICE


def test_financial_posting_gate_not_changed():
    posting=(Path(__file__).resolve().parents[1]/"services/rollover_compensation_posting.py").read_text()
    body=posting.split('def post_rollover_compensation(',1)[1]
    assert body.index('status_code=503') < body.index('db.query(')
