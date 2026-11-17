"""Regression contracts for the one-next-payment-per-loan report.

These tests protect critical business rules without using production financial data.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "apps/backend/routers/folio_book_reports.py"
CLIENT = ROOT / "apps/frontend/api/folioBook.ts"
SCREEN = ROOT / "apps/frontend/app/(dashboard)/company/folio-book/page.tsx"


def test_report_selects_earliest_unpaid_installment_before_date_filter() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert '@router.get("/next-installments.pdf")' in source
    assert "RepaymentInstallment.is_superseded.is_(False)" in source
    assert "RepaymentInstallment.total_due > RepaymentInstallment.paid_amount" in source
    assert "RepaymentInstallment.due_date.asc()" in source
    assert "next_by_loan.setdefault(installment.loan_id, installment)" in source
    assert source.index("next_by_loan.setdefault(") < source.index("if from_date and due < from_date:")


def test_report_restricts_company_scope_and_caps_amount_at_balance() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    report = source.split('@router.get("/next-installments.pdf")', 1)[1]
    assert "require_tenant_roles(context, COMPANY_ROLES)" in report
    assert "_base_query(db, context)" in report
    assert "ClientCompanyLoan.balance > 0" in report
    assert 'ClientCompanyLoan.status.in_(["active", "defaulted"])' in report
    assert 'Decimal(loan.balance or 0)' in report
    assert "min(" in report
    assert '"Cache-Control": "no-store"' in report


def test_report_filters_are_wired_from_existing_folio_screen() -> None:
    client = CLIENT.read_text(encoding="utf-8")
    screen = SCREEN.read_text(encoding="utf-8")
    assert '"/folio-book/next-installments.pdf"' in client
    for name in ("search", "group_code", "status", "from_date", "through_date"):
        assert name in client
        assert name in screen
    assert "downloadFolioNextInstallmentsPdf" in screen


def test_next_installments_default_to_new_disbursements_from_september_2026() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    report = source.split('@router.get("/next-installments.pdf")', 1)[1]
    assert "loan_from_date: date = Query(default=date(2026, 9, 1))" in report
    assert "ClientCompanyLoan.disbursed_at.is_not(None)" in report
    assert "ClientCompanyLoan.disbursed_at >= loan_from_date" in report
    assert "loan_from_date=loan_from_date" in report
    pdf_source = (ROOT / "apps/backend/services/folio_next_installment_report_service.py").read_text(encoding="utf-8")
    assert "loan disbursed from {loan_from_date.isoformat()}" in pdf_source
