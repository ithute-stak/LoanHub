"""Contract-level regression for pre-disbursement loan cancellation."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROUTE = (BACKEND / "routers/loans.py").read_text()
FRONTEND = BACKEND.parent / "frontend"
API = (FRONTEND / "api/loans.ts").read_text()
PAGE = (FRONTEND / "app/(dashboard)/company/loans/page.tsx").read_text()


def _cancel_route():
    return ROUTE.split("def cancel_approved_undisbursed_loan(", 1)[1].split("@router.", 1)[0]


def test_only_owner_or_admin_can_cancel_approved_undisbursed_loan():
    section = _cancel_route()
    assert "UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN" in section
    assert "ClientCompanyLoan.company_id == context.company_id" in section
    assert "with_for_update().first()" in section
    assert "assert_branch_scope(context, loan.branch_id)" in section
    assert "loan.status != LoanStatus.APPROVED" in section
    assert "loan.disbursed_at is not None" in section
    assert "loan.disbursed_by_user_id is not None" in section


def test_money_movements_and_external_mandates_fail_closed():
    section = _cancel_route()
    assert "PaymentTransaction.loan_id == loan.id" in section
    assert "CDASDeductionMandate.loan_id == loan.id" in section
    assert "LoanTopUpSettlement.new_loan_id == loan.id" in section
    assert "LoanTopUpSettlement.parent_loan_id == loan.id" in section
    assert "Decimal(loan.amount_paid or 0)" in section
    assert "Decimal(item.paid_amount or 0)" in section
    assert "confirm_no_disbursement" in section
    assert "signed_termination_reference" in section


def test_audit_and_signatures_are_retained():
    section = _cancel_route()
    assert "loan.status = LoanStatus.CANCELLED" in section
    assert 'contract.status = "cancelled"' in section
    assert 'linked_application.status = "cancelled"' in section
    assert 'action="loan.approved_undisbursed_cancelled"' in section
    assert '"contract_hash": contract.contract_hash' in section
    assert "db.delete(" not in section
    assert "contract.borrower_signed_at =" not in section
    assert "contract.company_signed_at =" not in section
    assert "loan.balance =" not in section


def test_loans_and_contracts_cancellation_interface():
    assert "cancelApprovedUndisbursedLoan" in API
    assert "/cancel-before-disbursement" in API
    assert "Cancel approved undisbursed loan" in PAGE
    assert "signed_termination_reference" in PAGE
    assert "confirm_no_disbursement: true" in PAGE
