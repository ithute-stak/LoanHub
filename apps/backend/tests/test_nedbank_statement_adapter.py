"""Synthetic, non-identifying regression tests for native Nedbank PDF layout."""
from dataclasses import replace
from decimal import Decimal

import pytest

from services.nedbank_statement_adapter import (
    NedbankStatementError,
    parse_nedbank_layout,
    validate_nedbank_series,
)


def _layout(month="August", year=2026, opening="100.00", ending="140.00"):
    return f""" {month} {year} Statement

Account Number: 12345678901                           Opening Balance: {opening}
Currency: LSL                                         Closing Balance: {ending}
Customer Id: 123456
Customer Name: EXAMPLE CUSTOMER
Account Name:
Branch Code: 507

 Transaction     Value Date    Reference         Description           Debit       Credit       Balance
2026-08-02       2026-08-01    852POSP1234567    SHOP                 10.00                    90.00
2026-08-28       2026-08-28    000INPT1234567    SAMPLE INCOME                     50.00      140.00
"""


def test_reads_two_column_headers_and_running_transactions():
    statement = parse_nedbank_layout(_layout())
    assert statement.account_number == "12345678901"
    assert statement.customer_name == "EXAMPLE CUSTOMER"
    assert statement.opening_balance == Decimal("100.00")
    assert statement.closing_balance == Decimal("140.00")
    assert len(statement.rows) == 2
    assert statement.total_debits == Decimal("10.00")
    assert statement.total_credits == Decimal("50.00")
    assert statement.reconciled and statement.review_required


def test_rejects_changed_balance_even_if_final_balance_is_unchanged():
    with pytest.raises(NedbankStatementError, match="running balance"):
        parse_nedbank_layout(_layout().replace("90.00", "89.00"))


def test_rejects_missing_transaction_even_if_closing_balance_is_printed():
    with pytest.raises(NedbankStatementError):
        parse_nedbank_layout(_layout().replace(
            "2026-08-28       2026-08-28    000INPT1234567    SAMPLE INCOME                     50.00      140.00",
            "",
        ))


def test_rejects_malformed_dated_row():
    with pytest.raises(NedbankStatementError, match="unparseable dated"):
        parse_nedbank_layout(_layout() + "\n2026-08-29 2026-08-29 INVALID-ROW\n")


def test_rejects_unknown_account_currency():
    with pytest.raises(NedbankStatementError, match="unsupported currency"):
        parse_nedbank_layout(_layout().replace("Currency: LSL", "Currency: USD"))


def test_series_requires_continuity_and_same_account():
    august = parse_nedbank_layout(_layout())
    september = replace(august, statement_month=9, opening_balance=august.closing_balance)
    assert validate_nedbank_series([august, september])
    assert not validate_nedbank_series([august, replace(september, account_number="999999999")])
    assert not validate_nedbank_series([august, replace(september, opening_balance=Decimal("1"))])
    assert not validate_nedbank_series([august, august])
