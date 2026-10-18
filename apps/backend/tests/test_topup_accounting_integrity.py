"""Top-up accounting safeguards: closing a refinanced loan isn't a cash repayment."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "services/loan_service.py").read_text()


def test_refinancing_preserves_actual_cash_paid():
    section = SOURCE.split("if loan.is_top_up:", 2)[-1].split("record_payment_accounting(db, payment)", 1)[0]
    assert "parent.amount_paid = money(parent.total_repayable)" not in section
    assert "parent.balance = money(0)" in section
    assert "parent.status = LoanStatus.COMPLETED" in section
    assert "parent_amount_paid_before=money(parent.amount_paid)" in section
    assert "settlement_amount=settlement_amount" in section


def test_disbursement_fails_closed_if_settlement_changes():
    section = SOURCE.split("def disburse_cash_loan(", 1)[1].split("def record_borrower_request_fee(", 1)[0]
    assert "with_for_update()" in section
    assert "preview_top_up_settlement(" in section
    assert "abs(settlement_amount - configured_settlement) > MONEY" in section
    assert "LoanTopUpSettlement" in section
    assert "if not existing_settlement:" in section


def test_refinancing_requires_same_tenant_borrower_and_balanced_cash():
    section = SOURCE.split("def disburse_cash_loan(", 1)[1].split("def record_borrower_request_fee(", 1)[0]
    assert "parent.company_id != loan.company_id or parent.borrower_id != loan.borrower_id" in section
    assert "money(loan.principal_amount) != money(loan.top_up_settlement_amount) + money(disbursement_amount)" in section
