from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from database.schemas.accounting import FixedAssetCreate, VatTransactionCreate
from services.accounting_service import (
    COMPANY_CHART,
    PLATFORM_CHART,
    calculate_fixed_asset_depreciation,
)


ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def _chart_map(rows):
    return {code: (name, account_type, normal_balance) for code, name, account_type, normal_balance in rows}


def test_company_chart_supports_full_financial_accounting_cycle():
    chart = _chart_map(COMPANY_CHART)

    assert chart["1000"][1:] == ("asset", "debit")
    assert chart["1100"][1:] == ("asset", "debit")
    assert chart["1210"][1:] == ("asset", "credit")  # contra receivable
    assert chart["1400"][1:] == ("asset", "debit")   # prepayments
    assert chart["1510"][1:] == ("asset", "credit")  # accumulated depreciation
    assert chart["1600"][1:] == ("asset", "debit")   # input VAT
    assert chart["2100"][1:] == ("liability", "credit")  # accruals
    assert chart["2200"][1:] == ("liability", "credit")  # output VAT
    assert chart["2990"][1:] == ("liability", "credit")  # suspense
    assert chart["4000"][1:] == ("revenue", "credit")
    assert chart["5400"][1:] == ("expense", "debit")
    assert chart["5500"][1:] == ("expense", "debit")


def test_platform_chart_keeps_double_entry_statement_classes():
    chart = _chart_map(PLATFORM_CHART)
    assert {value[1] for value in chart.values()} >= {"asset", "liability", "equity", "revenue", "expense"}


def test_vat_schema_accepts_registered_purchase():
    item = VatTransactionCreate(
        transaction_type="expense",
        net_amount=Decimal("100.00"),
        vat_amount=Decimal("15.00"),
        account_code="6500",
        settlement_account_code="1010",
        vat_registered=True,
        description="Office expense",
    )
    assert item.net_amount == Decimal("100.00")
    assert item.vat_amount == Decimal("15.00")


def test_vat_schema_rejects_unknown_transaction_type():
    with pytest.raises(ValidationError):
        VatTransactionCreate(
            transaction_type="loan",
            net_amount=Decimal("100.00"),
            vat_amount=Decimal("0.00"),
            account_code="1100",
            description="Invalid VAT classification",
        )


def test_trial_balance_keeps_debit_minus_credit_and_statements_present_credit_classes():
    source = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert "balance = debit - credit" in source
    assert 'line.account_type in {"liability", "equity", "revenue"}' in source


def test_period_close_requires_reconciliation_batches_closed():
    source = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert "ReconciliationBatch" in source
    assert '"reconciliation_batches_closed"' in source
    assert '"open_reconciliation_batches"' in source


def test_fixed_asset_schema_requires_rate_for_reducing_balance():
    with pytest.raises(ValidationError):
        FixedAssetCreate(
            reference="FA-001",
            name="Laptop",
            acquisition_date=date(2026, 1, 1),
            cost=Decimal("12000.00"),
            residual_value=Decimal("0"),
            useful_life_years=3,
            depreciation_method="reducing_balance",
        )


def test_straight_line_asset_depreciation_uses_cost_less_residual_value():
    asset = SimpleNamespace(
        amount=Decimal("22000.00"),
        status="active",
        data={
            "acquisition_date": "2026-01-01",
            "residual_value": "2000.00",
            "useful_life_years": 4,
            "depreciation_method": "straight_line",
            "depreciation_rate": None,
            "accumulated_depreciation": "0.00",
            "last_depreciation_date": None,
        },
    )
    assert calculate_fixed_asset_depreciation(
        asset, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
    ) == Decimal("5000.00")


def test_reducing_balance_asset_depreciation_uses_opening_carrying_amount():
    asset = SimpleNamespace(
        amount=Decimal("10000.00"),
        status="active",
        data={
            "acquisition_date": "2026-01-01",
            "residual_value": "0.00",
            "useful_life_years": 10,
            "depreciation_method": "reducing_balance",
            "depreciation_rate": "20",
            "accumulated_depreciation": "2000.00",
            "last_depreciation_date": "2026-12-31",
        },
    )
    assert calculate_fixed_asset_depreciation(
        asset, period_start=date(2027, 1, 1), period_end=date(2027, 12, 31)
    ) == Decimal("1600.00")


def test_fixed_asset_disposal_accounts_exist():
    chart = _chart_map(COMPANY_CHART)
    assert chart["4910"][1:] == ("revenue", "credit")
    assert chart["6510"][1:] == ("expense", "debit")


def test_credit_loss_accounts_are_part_of_unified_chart():
    chart = _chart_map(COMPANY_CHART)
    assert chart["1150"][1:] == ("asset", "credit")
    assert chart["5510"][1:] == ("expense", "debit")
    assert chart["6700"][0] == "Credit Bureau Expense"


def test_payment_accounting_posts_only_successful_transactions():
    source = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "if payment.status != PaymentStatus.SUCCEEDED:" in source
    assert 'reference_type="loan_write_off"' in source
    assert '"Collections must mark the loan written_off' in source


def test_loan_receivables_control_endpoint_is_exposed():
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert '@router.get("/controls/loan-receivables")' in router
    assert '@router.post("/write-offs/loans"' in router


def test_period_close_pack_enforces_adjustments_controls_and_reconciliation():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    governance = (ROOT / "backend" / "routers" / "governance_controls.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")

    assert "def period_close_pack(" in service
    assert '"fixed_asset_depreciation_complete"' in service
    assert '"credit_loss_provision_posted"' in service
    assert '"loan_receivables_control_balanced"' in service
    assert '"bank_statement_exceptions_cleared"' in service
    assert '@router.get("/period-close-pack")' in router
    assert '@router.post("/assets/depreciate-period")' in router
    assert 'if not pack["ready_to_lock"]:' in governance
    assert '"failed_checks"' in governance


def test_period_adjustments_support_next_period_reversal():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert "def reverse_period_adjustment(" in service
    assert '{"accrual_adjustment", "prepayment_adjustment"}' in service
    assert 'reference_type="period_adjustment_reversal"' in service
    assert '@router.post("/adjustments/{entry_id}/reverse"' in router


def test_cash_flow_engine_is_explicit_and_reconciles_to_ledger_cash():
    source = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "def _cash_flow_section(" in source
    assert '"lending_business_cash_flow"' in source
    assert '"tenant_lending_cash_flows": "operating"' in source
    assert '"reconciliation_difference"' in source
    assert '"reconciled": reconciliation_difference == 0' in source
    assert '"cash_flow_reconciled": bool(cash_flow["reconciled"])' in source


def test_statement_of_financial_position_includes_unclosed_profit_in_equity():
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert '"current_earnings"' in router
    assert '"total_equity"' in router
    assert 'totals["net_assets"] - totals["total_equity"]' in router
    assert '@router.get("/statement-of-changes-in-equity")' in router
    assert '"profit_or_loss_for_period"' in router
    assert '"drawings_and_distributions"' in router


def test_money_sources_are_accrued_at_source_and_coverage_is_enforced():
    accounting = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    finance = (ROOT / "backend" / "services" / "platform_finance_service.py").read_text(encoding="utf-8")
    bureau = (ROOT / "backend" / "services" / "credit_bureau_payg_service.py").read_text(encoding="utf-8")
    cdas = (ROOT / "backend" / "services" / "platform_cdas_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")

    assert "def record_platform_transaction_charge_accrual(" in accounting
    assert "def record_credit_bureau_transaction_accrual(" in accounting
    assert "def reverse_credit_bureau_transaction_accrual(" in accounting
    assert "def record_cdas_transaction_accrual(" in accounting
    assert "def reverse_cdas_transaction_accrual(" in accounting
    assert "record_platform_transaction_charge_accrual(db, entry)" in finance
    assert "record_credit_bureau_transaction_accrual(db, transaction)" in bureau
    assert "reverse_credit_bureau_transaction_accrual(db, row)" in bureau
    assert "record_cdas_transaction_accrual(db, row)" in cdas
    assert "reverse_cdas_transaction_accrual(db, row)" in cdas
    assert "def transaction_accounting_coverage(" in accounting
    assert '"transaction_accounting_coverage_complete"' in accounting
    assert '@router.get("/controls/transaction-coverage")' in router


def test_invoices_do_not_duplicate_usage_accruals():
    bureau = (ROOT / "backend" / "services" / "credit_bureau_payg_service.py").read_text(encoding="utf-8")
    cdas = (ROOT / "backend" / "services" / "platform_cdas_service.py").read_text(encoding="utf-8")
    assert "record_credit_bureau_invoice_accrual(db, invoice)" not in bureau
    assert "record_cdas_invoice_accrual(db, invoice)" not in cdas
    assert "Only an accrued, not-yet-invoiced Credit Bureau transaction can be waived" in bureau


def test_payment_channels_use_distinct_settlement_accounts():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert '("1020", "Electronic Payment Clearing", "asset", "debit")' in service
    assert 'if value == PaymentMethod.CASH.value:' in service
    assert 'if value == PaymentMethod.BANK.value:' in service
    assert 'return "1020"' in service
    assert 'account_by_code(db, key, "1020").id' in service


def test_direct_debit_requires_allocations_before_repayment_accounting():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "payment.purpose == PaymentPurpose.DIRECT_DEBIT" in service
    assert "PaymentAllocation.payment_id == payment.id" in service


def test_provider_invoice_settlements_are_in_transaction_coverage():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "PlatformCreditBureauInvoice" in service
    assert "PlatformCdasInvoice" in service
    assert '"credit_bureau_invoice_payments"' in service
    assert '"credit_bureau_platform_receipts"' in service
    assert '"cdas_invoice_payments"' in service
    assert '"cdas_platform_receipts"' in service


def test_payment_reversal_cascades_to_transaction_charge_and_uses_original_lines():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "def record_reversal_accounting(" in service
    assert 'reference_type="platform_transaction_charge_accrual"' in service
    assert 'charge.status = "reversed"' in service
    assert '"accounting_reversal"' in service
    assert '"debit": line.credit' in service
    assert '"credit": line.debit' in service


def test_written_off_loan_recovery_has_dedicated_income_and_evidence_controls():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    schemas = (ROOT / "backend" / "database" / "schemas" / "accounting.py").read_text(encoding="utf-8")
    chart = _chart_map(COMPANY_CHART)

    assert chart["4300"][1:] == ("revenue", "credit")
    assert "def record_written_off_loan_recovery(" in service
    assert '"written_off_loan_recovery"' in service
    assert '"Recovery exceeds the principal amount derecognised by the write-off journal"' in service
    assert '@router.post("/recoveries/written-off-loans"' in router
    assert "class WrittenOffLoanRecoveryCreate" in schemas
    assert "Non-cash recoveries require a proof_reference" in schemas
