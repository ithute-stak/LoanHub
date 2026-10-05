from decimal import Decimal

import pytest
from pydantic import ValidationError

from database.schemas.accounting import VatTransactionCreate
from services.accounting_service import COMPANY_CHART, PLATFORM_CHART


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
