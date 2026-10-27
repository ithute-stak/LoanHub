"""The approved final rollover posts a linked receivable, not a cash repayment."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
POSTING = (ROOT / "apps/backend/services/final_installment_rollover_posting.py").read_text()
ROUTER = (ROOT / "apps/backend/routers/loans.py").read_text()


def test_posting_is_serialized_and_debt_neutral():
    assert ".with_for_update()" in POSTING
    assert "ClientCompanyLoan.parent_loan_id == parent_id" in POSTING
    assert "validate_rollover_receivable_transfer(plan=plan" in POSTING
    assert 'principal_amount=outstanding' in POSTING
    assert 'interest_rate=Decimal("0")' in POSTING
    assert 'processing_fee=Decimal("0")' in POSTING
    assert 'total_repayable=outstanding' in POSTING
    assert 'parent.balance = Decimal("0")' in POSTING
    assert 'parent.total_repayable = parent.amount_paid' in POSTING
    assert "row.is_superseded = True" in POSTING
    assert "db.commit()" in POSTING
    assert "PaymentTransaction(" not in POSTING
    assert "CashTransaction(" not in POSTING


def test_original_payment_allocations_remain_unmodified():
    assert "PaymentAllocation(" not in POSTING
    assert "row.paid_amount =" not in POSTING
    assert '"original": original' in POSTING
    assert "loan.final_installment_receivable_transferred" in POSTING


def test_owner_only_post_and_signed_terms():
    section = ROUTER.split('def post_final_rollover_transfer(', 1)[1].split('@router.post("/{loan_id}/installments/final-rollover-transfer-plan")', 1)[0]
    assert "require_tenant_roles(context, {UserRole.COMPANY_OWNER})" in section
    assert "post_final_rollover(" in section
    assert "agreement_reference=payload.agreement_reference" in section
    assert "approval_reference=payload.approval_reference" in section
