"""Source-contract coverage for complete CDAS PAYG billing."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT.parent / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cdas_billing_migration_extends_platform_cdas_head() -> None:
    migration = _read(ROOT / "alembic/versions/c0e4g6h8j012_cdas_billing_completeness.py")

    assert 'revision = "c0e4g6h8j012"' in migration
    assert 'down_revision = "b9d3f5g7h911"' in migration
    assert '"platform_cdas_invoices"' in migration
    assert '"billing_due_days"' in migration
    assert '"refunded_at"' in migration
    assert '"refund_reason"' in migration


def test_cdas_monthly_invoices_waivers_refunds_and_overdue_controls_exist() -> None:
    service = _read(ROOT / "services/platform_cdas_service.py")
    scheduler = _read(ROOT / "services/cdas_billing_scheduler.py")
    main = _read(ROOT / "main.py")
    platform_router = _read(ROOT / "routers/platform_cdas.py")

    assert "def create_invoice(" in service
    assert "def waive_transaction(" in service
    assert "def refund_transaction(" in service
    assert "def run_monthly_invoice_cycle(" in service
    assert "def suspend_overdue_accounts(" in service
    assert "Notification(" in service
    assert "start_cdas_billing_scheduler" in main
    assert "stop_cdas_billing_scheduler" in main
    assert "run_monthly_invoice_cycle" in scheduler
    assert "suspend_overdue_accounts" in scheduler
    assert '@router.post("/transactions/{transaction_id}/waive")' in platform_router
    assert '@router.post("/transactions/{transaction_id}/refund")' in platform_router
    assert '@router.post("/invoices/{company_id}")' in platform_router
    assert '@router.post("/invoices/{invoice_id}/paid")' in platform_router


def test_cdas_invoices_use_snapshotted_operation_prices_and_transaction_states() -> None:
    service = _read(ROOT / "services/platform_cdas_service.py")

    assert 'PlatformCdasTransaction.status.in_(("accrued", "waived"))' in service
    assert '"operation_pricing_is_snapshotted_per_transaction": True' in service
    assert 'row.status = "invoiced"' in service
    assert 'row.status = "settled"' in service
    assert 'row.status = "refunded"' in service
    assert "Only a settled CDAS transaction can be refunded" in service


def test_cdas_outstanding_balance_includes_invoiced_usage_until_paid() -> None:
    service = _read(ROOT / "services/platform_cdas_service.py")

    assert 'PlatformCdasTransaction.status.in_(("accrued", "invoiced"))' in service
    assert "outstanding_balance(db, company_id=invoice.company_id)" in service
    assert 'subscription.status = "approved"' in service


def test_cdas_billing_posts_double_entry_accounting() -> None:
    accounting = _read(ROOT / "services/accounting_service.py")
    service = _read(ROOT / "services/platform_cdas_service.py")

    assert '("6800", "CDAS Service Expense", "expense", "debit")' in accounting
    assert '("4600", "CDAS Service Revenue", "revenue", "credit")' in accounting
    assert '("1200", "Tenant Receivables", "asset", "debit")' in accounting
    assert "def record_cdas_invoice_accrual" in accounting
    assert "def record_cdas_invoice_payment" in accounting
    assert "def record_cdas_transaction_refund" in accounting
    assert "record_cdas_invoice_accrual(db, invoice)" in service
    assert "record_cdas_invoice_payment(db, invoice)" in service
    assert "record_cdas_transaction_refund(db, row)" in service


def test_cdas_company_can_read_invoices_without_financial_mutation() -> None:
    router = _read(ROOT / "routers/cdas_api.py")
    settings = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/company/settings/_components/company-cdas-settings.tsx"
    )

    assert '@router.get("/invoices")' in router
    assert "list_cdas_invoices(db, company_id=context.company_id" in router
    assert 'api.get<CdasInvoice[]>("/cdas/invoices?limit=12")' in settings
    assert "CDAS invoices" in settings
    assert "Monthly Live PAYG statements" in settings


def test_cdas_platform_owner_controls_billing_due_terms() -> None:
    router = _read(ROOT / "routers/platform_cdas.py")
    service = _read(ROOT / "services/platform_cdas_service.py")
    page = _read(
        FRONTEND_ROOT
        / "app/(dashboard)/superadmin/control/integrations/cdas/page.tsx"
    )

    assert "billing_due_days: int = Field(default=14, ge=1, le=90)" in router
    assert "billing_due_days=payload.billing_due_days" in router
    assert "row.billing_due_days = max(1, min(int(billing_due_days), 90))" in service
    assert "Invoice due days" in page
    assert "billing_due_days: Number(billingDueDays || 14)" in page


def test_cdas_test_operations_remain_free_and_only_live_is_invoiced() -> None:
    service = _read(ROOT / "services/platform_cdas_service.py")

    assert 'rate = _money(normalize_pricing(subscription.pricing).get(operation_type, 0)) if live else Decimal("0.00")' in service
    assert '"accrued" if live and rate > 0 else ("free_live" if live else "test")' in service
    assert 'PlatformCdasTransaction.environment == "live"' in service
