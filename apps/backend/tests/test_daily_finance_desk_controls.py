"""Daily cash and legacy folio workflows are tenant-scoped and avoid inventing repayments."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTING = (ROOT / "routers/accounting.py").read_text()
UI = (ROOT.parent / "frontend/app/(dashboard)/company/finance-desk/page.tsx").read_text()


def test_cash_count_has_one_branch_day_reference_and_closing_snapshot():
    assert 'f"cash-day:{branch or \'company\'}:{payload.business_date.isoformat()}"' in ACCOUNTING
    assert 'CompanyOperatingRecord.module == "cash_control"' in ACCOUNTING
    assert 'with_for_update().first()' in ACCOUNTING
    assert '"expected_closing_at_confirmation"' in ACCOUNTING
    assert '"variance_at_confirmation"' in ACCOUNTING
    assert 'record.branch_id != context.branch_id' in ACCOUNTING


def test_legacy_folio_cash_is_suspense_not_a_loan_repayment():
    section = ACCOUNTING.split("class LegacyFolioReceiptCreate(BaseModel):", 1)[1].split('@router.get("/daily-cash")', 1)[0]
    assert 'credit_code="2990"' in section
    assert '"cash": "1000", "bank": "1010", "electronic": "1020"' in section
    assert '"legacy_folio_receipt"' in section
    assert 'UserRole.BRANCH_MANAGER' not in section or 'CASHIER_ROLES' in section
    assert "loan.balance =" not in section


def test_live_ui_uses_real_services_and_branch_scope():
    assert 'api.post("/accounting/expenses"' in UI
    assert 'api.post("/accounting/legacy-folio-receipts"' in UI
    assert 'api.post("/accounting/daily-cash/open"' in UI
    assert 'branch_id: selectedBranchId' in UI
    assert 'listJournalEntries({ fromDate: rangeStart, toDate: asOf, branchId: selectedBranchId, limit: 500 })' in UI
    assert 'api.get<FinanceReport>("/accounting/daily-finance/report"' in UI
    assert 'Number(report?.disbursements.amount ?? 0)' in UI
    assert 'Number(report?.repayments.amount ?? 0)' in UI


def test_server_report_aggregates_all_successful_payment_records():
    assert 'PaymentTransaction.status == PaymentStatus.SUCCEEDED' in ACCOUNTING
    assert 'PaymentPurpose.LOAN_DISBURSEMENT' in ACCOUNTING
    assert 'PaymentPurpose.LOAN_REPAYMENT' in ACCOUNTING
    assert 'func.coalesce(func.sum(PaymentTransaction.amount), 0)' in ACCOUNTING
