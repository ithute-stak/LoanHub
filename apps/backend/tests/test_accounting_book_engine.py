from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from database.models.enums import PaymentMethod
from database.schemas.accounting import FixedAssetCreate, VatTransactionCreate
from services.accounting_service import (
    COMPANY_CHART,
    PLATFORM_CHART,
    _cash_flow_section,
    _validate_normalized_journal_lines,
    assess_capital_expenditure,
    calculate_fixed_asset_depreciation,
    value_inventory_lower_of_cost_and_nrv,
    settlement_account_code,
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


def test_double_entry_invariant_requires_two_lines_and_two_accounts():
    with pytest.raises(Exception) as one_line:
        _validate_normalized_journal_lines([
            {"account_id": "cash", "debit": Decimal("100.00"), "credit": Decimal("0.00")},
        ])
    assert "at least two lines" in str(one_line.value.detail)

    with pytest.raises(Exception) as same_account:
        _validate_normalized_journal_lines([
            {"account_id": "cash", "debit": Decimal("100.00"), "credit": Decimal("0.00")},
            {"account_id": "cash", "debit": Decimal("0.00"), "credit": Decimal("100.00")},
        ])
    assert "at least two accounts" in str(same_account.value.detail)


def test_double_entry_invariant_requires_equal_positive_debits_and_credits():
    with pytest.raises(Exception) as unbalanced:
        _validate_normalized_journal_lines([
            {"account_id": "cash", "debit": Decimal("100.00"), "credit": Decimal("0.00")},
            {"account_id": "capital", "debit": Decimal("0.00"), "credit": Decimal("90.00")},
        ])
    assert "debits and credits must be equal" in str(unbalanced.value.detail)

    debit, credit = _validate_normalized_journal_lines([
        {"account_id": "bank", "debit": Decimal("100.00"), "credit": Decimal("0.00")},
        {"account_id": "principal", "debit": Decimal("0.00"), "credit": Decimal("70.00")},
        {"account_id": "interest", "debit": Decimal("0.00"), "credit": Decimal("30.00")},
    ])
    assert debit == Decimal("100.00")
    assert credit == Decimal("100.00")


def test_manual_posting_revalidates_persisted_journal_integrity():
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "def validate_postable_entry(" in service
    assert "validate_postable_entry(db, entry)" in router
    assert "Journal header totals do not match persisted journal lines" in service


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


def test_income_statement_exposes_gross_result_and_operating_expenses():
    source = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert 'totals["gross_result"]' in source
    assert 'totals["operating_expenses"]' in source
    assert 'line.code == "5000"' in source
    assert 'totals["net_profit"] = revenue_total - expense_total' in source


def test_statement_of_financial_position_exposes_working_capital_and_equation_check():
    source = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert "CURRENT_ASSET_CODES" in source
    assert "NON_CURRENT_ASSET_CODES" in source
    assert "CURRENT_LIABILITY_CODES" in source
    assert 'totals["working_capital"]' in source
    assert 'totals["accounting_equation_difference"]' in source
    assert 'totals["equity_check"] = totals["accounting_equation_difference"]' in source


def test_unknown_user_accounts_are_not_silently_misclassified_by_liquidity():
    source = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert 'return "unclassified_asset"' in source
    assert 'return "unclassified_liability"' in source


def test_period_close_requires_reconciliation_batches_closed():
    source = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert "ReconciliationBatch" in source
    assert '"reconciliation_batches_closed"' in source
    assert '"open_reconciliation_batches"' in source


def test_inventory_valuation_uses_lower_of_cost_and_nrv_item_by_item():
    result = value_inventory_lower_of_cost_and_nrv([
        {"reference": "A", "cost": Decimal("100"), "expected_selling_price": Decimal("150"), "costs_to_sell": Decimal("0")},
        {"reference": "B", "cost": Decimal("120"), "expected_selling_price": Decimal("100"), "costs_to_sell": Decimal("10")},
    ])
    assert result["inventory_value"] == 190.0
    assert result["write_down"] == 30.0
    assert result["items"][0]["basis"] == "cost"
    assert result["items"][1]["basis"] == "net_realisable_value"


def test_capital_expenditure_assessment_separates_initial_use_from_maintenance():
    result = assess_capital_expenditure([
        {"description": "Machine", "amount": Decimal("10000"), "category": "purchase_price"},
        {"description": "Installation", "amount": Decimal("800"), "category": "assembly_installation"},
        {"description": "Annual service", "amount": Decimal("500"), "category": "repair_maintenance"},
    ])
    assert result["capital_expenditure"] == 10800.0
    assert result["revenue_expenditure"] == 500.0


def test_borrowing_cost_capitalisation_requires_both_conditions():
    denied = assess_capital_expenditure(
        [{"description": "Interest", "amount": Decimal("600"), "category": "borrowing_cost_construction"}],
        borrowing_costs_directly_attributable=True,
        asset_requires_substantial_time_to_prepare=False,
    )
    allowed = assess_capital_expenditure(
        [{"description": "Interest", "amount": Decimal("600"), "category": "borrowing_cost_construction"}],
        borrowing_costs_directly_attributable=True,
        asset_requires_substantial_time_to_prepare=True,
    )
    assert denied["revenue_expenditure"] == 600.0
    assert allowed["capital_expenditure"] == 600.0


def test_chapter_22_accrued_income_is_posted_and_reversible():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert '("1220", "Accrued Income", "asset", "debit")' in service
    assert "def post_accrued_income_adjustment(" in service
    assert 'debit_code="1220", credit_code=revenue_account_code' in service
    assert '"accrued_income_adjustment"' in service
    assert '@router.post("/adjustments/accrued-income"' in router


def test_chapters_18_20_calculators_are_exposed():
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert '@router.post("/inventory/valuation")' in router
    assert '@router.post("/capital-expenditure/assess")' in router


def test_current_asset_statement_includes_accrued_income():
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert '"1200", "1210", "1220", "1300"' in router


def test_chapters_23_27_controls_detect_balancing_and_non_balancing_errors():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert "def accounting_error_diagnostics(" in service
    assert "def incomplete_records_control(" in service
    assert "EXPECTED_REFERENCE_ACCOUNTS" in service
    assert '"possible_errors_not_revealed_by_trial_balance"' in service
    assert '"operational_sources_fully_accounted"' in service
    assert '"loan_receivables_control_balanced"' in service
    assert '"reconciliation_exceptions_cleared"' in service
    assert '@router.get("/controls/error-diagnostics")' in router
    assert '@router.get("/controls/incomplete-records")' in router


def test_error_diagnostics_preserves_book_warning_that_balanced_trial_balance_is_not_proof():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "A zero trial-balance difference does not prove that postings are correct" in service
    assert '"possible_error_of_principle_or_commission"' in service
    assert '"omission_via_source_coverage"' in service
    assert '"suspense_difference"' in service


def test_incomplete_records_control_uses_source_reconstruction_not_profit_guessing():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert '"method": "operational-source-to-double-entry reconstruction"' in service
    assert "does not estimate profit from single-entry statements of affairs" in service
    assert '"missing_source_ids": coverage["missing_source_ids"]' in service


def test_chapter_26_suspense_corrections_remain_journal_based():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "def post_suspense_correction(" in service
    assert 'reference_type="suspense_correction"' in service
    assert 'target_account_code == "2990"' in service


def test_chapter_28_cash_equivalents_exclude_unsettled_electronic_clearing():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert 'CASH_EQUIVALENT_CODES = {"1000", "1010"}' in service
    assert '"electronic_clearing": "excluded_until_settled_to_cash_or_bank"' in service
    assert 'for code in CASH_EQUIVALENT_CODES' in service


def test_chapter_29_receipts_and_payments_summary_is_cash_basis_only():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert "def receipts_and_payments_summary(" in service
    assert '"basis": "cash_book_summary"' in service
    assert "does not replace, LoanHub's accrual-basis income statement" in service
    assert '@router.get("/receipts-and-payments")' in router


def test_chapter_30_joint_venture_accounting_is_not_forced_into_core_lending():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "joint_venture" not in service.lower()


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


def test_books_of_original_entry_are_exposed_and_traceable():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")

    assert "def classify_book_of_original_entry(" in service
    assert "def books_of_original_entry(" in service
    assert "def source_book_traceability(" in service
    assert '"cash_book"' in service
    assert '"sales_day_book"' in service
    assert '"purchases_day_book"' in service
    assert '"journal"' in service
    assert '"source_reference_kind"' in service
    assert '"folio"' in service
    assert '@router.get("/books-of-original-entry")' in router
    assert '@router.get("/controls/source-book-traceability")' in router


def test_source_books_keep_lending_specific_classification_conservative():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert 'SETTLEMENT_BOOK_CODES = {"1000", "1010", "1020"}' in service
    assert 'RECEIVABLE_BOOK_CODES = {"1100", "1110", "1120", "1200"}' in service
    assert 'PAYABLE_BOOK_CODES = {"2000", "2100", "2300", "2400"}' in service
    assert 'return "journal", "adjustment, opening, correction or transaction outside specialist day books"' in service


def test_vat_engine_remains_book_aligned_for_registered_and_unregistered_entities():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "def post_vat_transaction(" in service
    assert "VAT-registered sale:" in service
    assert "VAT-registered purchase/expense/asset:" in service
    assert "Non-registered entities do not post VAT separately" in service


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


def test_provider_settlements_preserve_payment_channel_and_evidence():
    accounting = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    bureau = (ROOT / "backend" / "services" / "credit_bureau_payg_service.py").read_text(encoding="utf-8")
    cdas = (ROOT / "backend" / "services" / "platform_cdas_service.py").read_text(encoding="utf-8")
    bureau_router = (ROOT / "backend" / "routers" / "platform_credit_bureau.py").read_text(encoding="utf-8")
    cdas_router = (ROOT / "backend" / "routers" / "platform_cdas.py").read_text(encoding="utf-8")

    assert 'settlement.get("payment_method")' in accounting
    assert 'refund.get("payment_method")' in accounting
    assert 'snapshot["settlement"]' in bureau
    assert 'snapshot["settlement"]' in cdas
    assert "Non-cash invoice payments require proof_reference" in bureau
    assert "Non-cash invoice payments require proof_reference" in cdas
    assert 'metadata["refund"]' in cdas
    assert "Non-cash refunds require proof_reference" in cdas
    assert "class ProviderInvoiceSettlement" in bureau_router
    assert "class ProviderInvoiceSettlement" in cdas_router
    assert "class CdasTransactionRefund" in cdas_router


def test_credit_bureau_refunds_are_evidence_backed_and_accounted():
    accounting = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    bureau = (ROOT / "backend" / "services" / "credit_bureau_payg_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "platform_credit_bureau.py").read_text(encoding="utf-8")

    assert "def record_credit_bureau_transaction_refund(" in accounting
    assert "def refund_transaction(" in bureau
    assert "Only a settled Credit Bureau transaction can be refunded" in bureau
    assert "Non-cash refunds require proof_reference" in bureau
    assert 'metadata["refund"]' in bureau
    assert '@router.post("/experian/transactions/{transaction_id}/refund")' in router


def test_electronic_clearing_has_settlement_reconciliation_and_close_guard():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    schemas = (ROOT / "backend" / "database" / "schemas" / "accounting.py").read_text(encoding="utf-8")

    assert "class ElectronicClearingSettlementCreate" in schemas
    assert "def record_electronic_clearing_settlement(" in service
    assert "def electronic_clearing_reconciliation(" in service
    assert '("1010", "1020") if direction == "provider_to_bank"' in service
    assert '"electronic_clearing_reconciled": bool(electronic_clearing["balanced"])' in service
    assert '@router.get("/controls/electronic-clearing")' in router
    assert '@router.post("/controls/electronic-clearing/settlements"' in router


def test_electronic_clearing_reconciliation_includes_non_payment_sources():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert '"provider_invoice_net"' in service
    assert '"provider_refund_net"' in service
    assert '"opening_source_net"' in service
    assert '"electronic_provider_invoice_payments"' in service
    assert '"electronic_provider_refunds"' in service


def test_electronic_clearing_aging_identifies_stale_fifo_open_items():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")

    assert "ELECTRONIC_CLEARING_STALE_DAYS = 5" in service
    assert "def electronic_clearing_aging(" in service
    assert '"method": "fifo_open_item_aging"' in service
    assert '"age_basis": "calendar_days"' in service
    assert '"receivable_from_provider"' in service
    assert '"provider_prefunding_or_outbound"' in service
    assert '"stale_item_count"' in service
    assert '"has_stale_items": stale_count > 0' in service
    assert '@router.get("/controls/electronic-clearing/aging")' in router


def test_period_close_blocks_stale_electronic_clearing_items():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert '"electronic_clearing_has_no_stale_items": not bool(electronic_clearing_age["has_stale_items"])' in service
    assert '"electronic_clearing_aging": electronic_clearing_age' in service


def test_bank_reconciliation_matches_clearing_settlements_by_evidence():
    reconciliation = (ROOT / "backend" / "services" / "reconciliation_service.py").read_text(encoding="utf-8")
    assert "def _match_bank_line_to_clearing_settlement(" in reconciliation
    assert '"exact_clearing_settlement_provider_reference"' in reconciliation
    assert '"exact_clearing_settlement_proof_reference"' in reconciliation
    assert '"CLEARING_DIRECTION_MISMATCH"' in reconciliation
    assert '"MISSING_BANK_SETTLEMENT"' in reconciliation
    assert "missing_clearing_settlements_added" in reconciliation


def test_period_close_requires_clearing_settlement_bank_traceability():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert "def bank_settlement_chain(" in service
    assert '"bank_statement_matched"' in service
    assert '"clearing_settlements_bank_matched": bool(settlement_chain["complete"])' in service
    assert '"bank_settlement_chain": settlement_chain' in service
    assert '@router.get("/controls/bank-settlement-chain")' in router


def test_bank_statement_balances_reconcile_statement_arithmetic_to_account_1010():
    reconciliation = (ROOT / "backend" / "services" / "reconciliation_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "reconciliation.py").read_text(encoding="utf-8")

    assert "def set_bank_statement_balances(" in reconciliation
    assert "def bank_statement_balance_reconciliation(" in reconciliation
    assert '"statement_arithmetic_difference"' in reconciliation
    assert '"ledger_closing_balance"' in reconciliation
    assert '"statement_reconciled_to_ledger"' in reconciliation
    assert '"ledger_item_not_yet_on_bank_statement"' in reconciliation
    assert '"bank_statement_item_excluded_from_ledger"' in reconciliation
    assert 'detail={"message": "Bank statement balances do not reconcile to account 1010"' in reconciliation
    assert '@router.put("/batches/{batch_id}/bank-statement-balances")' in router
    assert '@router.get("/batches/{batch_id}/bank-balance-reconciliation")' in router


def test_period_close_requires_closed_balanced_bank_batch_when_bank_is_used():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert '"bank_statement_balance_reconciled"' in service
    assert '"bank_ledger_activity"' in service
    assert '"bank_opening"' in service
    assert '"bank_closing"' in service
    assert '"bank_statement_balance_reconciliation": bank_balance_control' in service
    assert 'ReconciliationBatch.source_type == "bank_statement"' in service
    assert 'ReconciliationBatch.status == "closed"' in service


def test_bank_statement_missing_items_use_maker_checker_accounting():
    reconciliation = (ROOT / "backend" / "services" / "reconciliation_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "reconciliation.py").read_text(encoding="utf-8")

    assert "def request_bank_statement_accounting_adjustment(" in reconciliation
    assert "def decide_bank_statement_accounting_adjustment(" in reconciliation
    assert '"bank_statement_accounting_adjustment"' in reconciliation
    assert '"BANK_ITEM_REQUIRES_ACCOUNTING"' in reconciliation
    assert '"maker_checker_bank_accounting"' in reconciliation
    assert 'if line.direction == "credit":' in reconciliation
    assert 'debit_code, credit_code = "1010", counterpart_code' in reconciliation
    assert 'debit_code, credit_code = counterpart_code, "1010"' in reconciliation
    assert '@router.post("/batches/{batch_id}/lines/{line_id}/bank-accounting-adjustment"' in router
    assert '"/bank-accounting-adjustment/{approval_id}/decision"' in router


def test_bank_statement_adjustment_rejects_cash_and_clearing_as_counterparts():
    reconciliation = (ROOT / "backend" / "services" / "reconciliation_service.py").read_text(encoding="utf-8")
    assert 'if counterpart.code in {"1000", "1010", "1020"}:' in reconciliation
    assert "Choose the actual income, expense, receivable, payable or equity counterpart account" in reconciliation


def test_canonical_bank_reconciliation_supersedes_legacy_bank_line_close_check():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "canonical_bank_batch_q" in service
    assert '"legacy_unmatched_bank_lines"' in service
    assert '"canonical_bank_batch_exists"' in service
    assert "True if canonical_bank_batch_exists else legacy_bank_unmatched_count == 0" in service


def test_chargebacks_and_direct_debits_reverse_the_original_loan_effects():
    loan_service = (ROOT / "backend" / "services" / "loan_service.py").read_text(encoding="utf-8")
    governance = (ROOT / "backend" / "services" / "governance_control_service.py").read_text(encoding="utf-8")
    gateway = (ROOT / "backend" / "services" / "lelefa_paygate_service.py").read_text(encoding="utf-8")
    router = (ROOT / "backend" / "routers" / "governance_controls.py").read_text(encoding="utf-8")

    assert "PaymentPurpose.DIRECT_DEBIT" in loan_service
    assert 'if adjustment.adjustment_type == "chargeback":' in governance
    assert 'allowed_statuses.add("under_investigation")' in governance
    assert "def complete_adjustment_for_provider_reversal(" in governance
    assert "complete_adjustment_for_provider_reversal(" in gateway
    assert '@router.post("/payment-adjustments/{adjustment_id}/provider-confirm")' in router


def test_loan_control_excludes_written_off_principal_and_includes_direct_debits():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert '"source_written_off_principal"' in service
    assert '"write_offs": write_off_count' in service
    assert "CollectionCase.write_off_at.is_not(None)" in service
    assert "loan_source_principal_outstanding(" in service
    assert "PaymentPurpose.DIRECT_DEBIT" in service


def test_post_writeoff_payments_route_to_recovery_income_not_receivable():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "written_off_case" in service
    assert 'description="Recovery received after loan write-off"' in service
    assert 'reference_type="payment_transaction"' in service
    assert 'credit_code="4300"' in service
    assert "recovery_payment_ids" in service


def test_written_off_recovery_balance_is_ledger_net_of_reversals():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert "def _written_off_recovery_balance(" in service
    assert 'JournalEntry.reference_id.like(f"reversal:written_off_loan_recovery:{loan_id}:%")' in service
    assert 'f"reversal:payment_transaction:{pid}"' in service
    assert "case.recovered_amount = _written_off_recovery_balance(" in service


def test_chart_upgrade_preserves_legacy_credit_loss_journal_semantics():
    service = (ROOT / "backend" / "services" / "accounting_service.py").read_text(encoding="utf-8")
    assert '"credit loss" in str(legacy_6700.name or "").lower()' in service
    assert 'legacy_6700.code = "5510"' in service
    assert 'JournalEntry.reference_type == "credit_loss_provision_run"' in service
    assert '{JournalLine.account_id: provision_5510.id}' in service
    assert 'by_code.pop("6700", None)' in service


def test_settlement_account_routing_executes_for_cash_bank_and_electronic_channels():
    assert settlement_account_code(PaymentMethod.CASH) == "1000"
    assert settlement_account_code(PaymentMethod.BANK) == "1010"
    assert settlement_account_code(PaymentMethod.LELEFAPAYGATE) == "1020"
    assert settlement_account_code("electronic") == "1020"


def test_cash_flow_policy_executes_explicit_lending_asset_and_equity_classification():
    payment_entry = SimpleNamespace(reference_type="payment_transaction")
    asset_entry = SimpleNamespace(reference_type="fixed_asset_acquisition")
    ordinary_entry = SimpleNamespace(reference_type="expense")

    assert _cash_flow_section(
        payment_entry, {"1100"}, company_id="tenant"
    ) == ("operating", "lending_business_cash_flow")
    assert _cash_flow_section(
        asset_entry, {"1500"}, company_id="tenant"
    ) == ("investing", "fixed_asset_transaction")
    assert _cash_flow_section(
        ordinary_entry, {"3000"}, company_id="tenant"
    ) == ("financing", "owner_equity_counterpart")
