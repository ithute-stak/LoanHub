"""Guard the monthly payment PDF contract and tenant-safe ledger filters."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTER = (ROOT / "apps/backend/routers/loans.py").read_text(encoding="utf-8")
REPORT = (ROOT / "apps/backend/services/monthly_loan_payment_report.py").read_text(encoding="utf-8")
PORTFOLIO = (ROOT / "apps/frontend/components/loans/loan-portfolio-workspace.tsx").read_text(encoding="utf-8")


def test_monthly_payment_report_is_tenant_scoped_and_month_bounded():
    assert '@router.get("/reports/monthly-payments.pdf")' in ROUTER
    assert 'PaymentTransaction.company_id == context.company_id' in ROUTER
    assert 'ClientCompanyLoan.company_id == context.company_id' in ROUTER
    assert 'ClientCompanyLoan.branch_id == context.branch_id' in ROUTER
    assert 'PaymentTransaction.completed_at >= start_utc' in ROUTER
    assert 'PaymentTransaction.completed_at < end_utc' in ROUTER
    assert 'PaymentTransaction.status == PaymentStatus.SUCCEEDED' in ROUTER
    assert 'PaymentTransaction.direction == PaymentDirection.INBOUND' in ROUTER
    assert 'PaymentTransaction.purpose == PaymentPurpose.LOAN_REPAYMENT' in ROUTER


def test_report_uses_existing_loanhub_document_branding_and_ledger_amounts():
    assert 'build_document(' in REPORT
    assert 'DocumentContext(db=db, company=company' in REPORT
    assert 'Decimal(str(p.amount))' in REPORT
    assert 'Loan Payment Report' in REPORT


def test_portfolio_has_month_picker_and_pdf_action():
    assert 'type="month" value={reportMonth}' in PORTFOLIO
    assert 'downloadMonthlyLoanPaymentsPdf(reportMonth)' in PORTFOLIO
    assert 'Monthly payments PDF' in PORTFOLIO
