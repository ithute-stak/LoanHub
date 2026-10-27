"""Regression contracts for cash-movement statement scope and rendering."""
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTER = (ROOT / "apps/backend/routers/loans.py").read_text()
SERVICE = (ROOT / "apps/backend/services/loan_period_statement_service.py").read_text()
UI = (ROOT / "apps/frontend/components/loans/loan-portfolio-workspace.tsx").read_text()


def test_statement_endpoint_is_company_scoped_and_period_bounded():
    assert '@router.get("/reports/loan-cash-statement.pdf")' in ROUTER
    assert 'require_tenant_roles(context,' in ROUTER
    assert 'branch_id = context.branch_id if context.role not in COMPANY_MANAGEMENT_ROLES else None' in ROUTER
    assert 'period == "weekly"' in ROUTER
    assert 'first = start - timedelta(days=start.weekday())' in ROUTER
    assert 'first = start.replace(day=1)' in ROUTER


def test_statement_includes_only_settled_loan_movements_and_opening_history():
    assert 'PaymentTransaction.status == PaymentStatus.SUCCEEDED' in SERVICE
    assert 'PaymentTransaction.completed_at < end_utc' in SERVICE
    assert 'PaymentTransaction.company_id == company_id' in SERVICE
    assert 'ClientCompanyLoan.company_id == company_id' in SERVICE
    assert 'PaymentPurpose.LOAN_REPAYMENT' in SERVICE
    assert 'PaymentPurpose.LOAN_DISBURSEMENT' in SERVICE
    assert 'opening = sum(' in SERVICE
    assert 'closing = opening + receipts - disbursed' in SERVICE
    assert 'not an accrual trial balance' in SERVICE


def test_portfolio_controls_allow_both_reporting_periods():
    assert 'Statement period' in UI
    assert '<SelectItem value="weekly">Weekly</SelectItem>' in UI
    assert '<SelectItem value="monthly">Monthly</SelectItem>' in UI
    assert 'downloadLoanCashStatementPdf(statementPeriod, statementDate)' in UI
