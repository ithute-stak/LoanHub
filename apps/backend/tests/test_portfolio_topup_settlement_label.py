"""The portfolio must distinguish a refinanced old loan from ordinary repayment."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "frontend/components/loans/loan-portfolio-workspace.tsx").read_text(encoding="utf-8")


def test_only_funded_linked_topup_may_label_original_facility_as_settled_via_topup():
    # A completed loan or zero balance alone is insufficient evidence.
    assert 'child.is_top_up' in SOURCE
    assert 'child.parent_loan_id' in SOURCE
    assert 'child.disbursed_at' in SOURCE
    assert '["active", "completed"].includes(child.status)' in SOURCE
    assert 'loan.status === "completed" && Number(loan.balance) <= 0.005' in SOURCE
    assert "fundedTopUpByParent.get(loan.id)" in SOURCE


def test_portfolio_explains_settlement_and_cross_references_replacement():
    assert "Settled via top-up" in SOURCE
    assert "Replaced by" in SOURCE
    assert "Top-up of" in SOURCE
    assert "/company/loans?folio=" in SOURCE
    assert "Internal settlement, not cash repaid" in SOURCE
    assert 'replacement ? "Refinanced"' in SOURCE


def test_normal_completed_loans_keep_normal_status_and_cash_repayment_progress():
    assert "{titleCase(loan.status)}" in SOURCE
    assert "!replacement ? <Progress" in SOURCE
    assert "loan.is_overdue" in SOURCE
