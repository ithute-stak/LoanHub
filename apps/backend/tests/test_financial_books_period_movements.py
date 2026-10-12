"""Check reconciliation with realistic opening balances and period activity."""
from decimal import Decimal

from services.financial_books_reconciliation import reconcile_books_pack


def test_opening_balances_and_opposing_movements_do_not_create_false_alarm():
    # Cash opens at 400, receives 250, pays 75. Liability opens at 400,
    # increases by 250, decreases by 75. Both net movements are 175.
    pack = {
        "trial_balance": {
            "total_debit": Decimal("325.00"),
            "total_credit": Decimal("325.00"),
            "difference": Decimal("0.00"),
            "lines": [
                {"account_id": "cash", "debit": Decimal("250"), "credit": Decimal("75")},
                {"account_id": "liability", "debit": Decimal("75"), "credit": Decimal("250")},
            ],
        },
        "general_ledger": [
            {"account_id": "cash", "normal_balance": "debit",
             "opening_balance": Decimal("400"), "closing_balance": Decimal("575")},
            {"account_id": "liability", "normal_balance": "credit",
             "opening_balance": Decimal("400"), "closing_balance": Decimal("575")},
        ],
    }
    assert reconcile_books_pack(pack)["reconciled"] is True


def test_period_net_mismatch_reports_specific_account():
    pack = {
        "trial_balance": {
            "total_debit": "10.00", "total_credit": "10.00", "difference": "0.00",
            "lines": [
                {"account_id": "a", "debit": "10.00", "credit": "0"},
                {"account_id": "b", "debit": "0", "credit": "10.00"},
            ],
        },
        "general_ledger": [
            {"account_id": "a", "normal_balance": "debit", "opening_balance": "50",
             "closing_balance": "61"},
            {"account_id": "b", "normal_balance": "credit", "opening_balance": "50",
             "closing_balance": "60"},
        ],
    }
    report = reconcile_books_pack(pack)
    assert report["reconciled"] is False
    assert "account_closing_balance_mismatch:a" in report["findings"]
