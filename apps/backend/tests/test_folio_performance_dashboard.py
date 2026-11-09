"""Folio performance boundaries and safeguards."""
from datetime import date
from pathlib import Path

from services.folio_performance_service import _month_bounds, _money

ROOT = Path(__file__).resolve().parents[3]


def test_month_bounds_include_year_rollover_and_leap_year():
    assert _month_bounds(date(2026, 11, 9)) == (date(2026, 11, 1), date(2026, 12, 1))
    assert _month_bounds(date(2026, 12, 31)) == (date(2026, 12, 1), date(2027, 1, 1))
    assert _month_bounds(date(2028, 2, 29)) == (date(2028, 2, 1), date(2028, 3, 1))


def test_currency_values_are_rounded_as_money():
    assert _money("10.125") == 10.12
    assert _money("15.50") == 15.5


def test_dashboard_uses_tenant_and_branch_scoped_queries_not_global_totals():
    src = (ROOT / "apps/backend/services/folio_performance_service.py").read_text()
    assert "ClientCompanyLoan.company_id == context.company_id" in src
    assert "ClientCompanyLoan.branch_id == context.branch_id" in src
    assert "PaymentTransaction.loan_id.in_(ids)" in src
    assert "PaymentTransaction.company_id == context.company_id" in src
    assert "PaymentTransaction.status == PaymentStatus.SUCCEEDED" in src
    assert "PaymentTransaction.direction == PaymentDirection.INBOUND" in src
    assert "PaymentTransaction.purpose == PaymentPurpose.LOAN_REPAYMENT" in src
    assert "RepaymentInstallment.is_superseded.is_(False)" in src


def test_dashboard_is_read_only_and_route_is_protected():
    service = (ROOT / "apps/backend/services/folio_performance_service.py").read_text()
    router = (ROOT / "apps/backend/routers/folio_book.py").read_text()
    page = (ROOT / "apps/frontend/app/(dashboard)/company/folio-book/performance/page.tsx").read_text()
    assert "db.commit(" not in service
    assert "db.add(" not in service
    assert '@router.get("/performance")' in router
    assert "require_tenant_roles(context, FOLIO_BOOK_ROLES)" in router
    assert "getFolioPerformance()" in page
    assert "Outstanding balance" in page
    assert "Overdue instalments" in page
