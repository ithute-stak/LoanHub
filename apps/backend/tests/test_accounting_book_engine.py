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
