"""Cross-book reconciliation must detect discrepancies without rewriting balances."""
from copy import deepcopy

from services.financial_books_reconciliation import reconcile_books_pack


def example_pack():
    return {
        "trial_balance": {
            "total_debit": "100.00",
            "total_credit": "100.00",
            "difference": "0.00",
            "lines": [
                {"account_id": "cash", "debit": "100.00", "credit": "0.00"},
                {"account_id": "capital", "debit": "0.00", "credit": "100.00"},
            ],
        },
        "general_ledger": [
            {"account_id": "cash", "normal_balance": "debit", "closing_balance": "100.00"},
            {"account_id": "capital", "normal_balance": "credit", "closing_balance": "100.00"},
        ],
    }


def test_balanced_books_reconcile_read_only():
    pack = example_pack()
    original = deepcopy(pack)
    assert reconcile_books_pack(pack) == {"reconciled": True, "findings": []}
    assert pack == original


def test_detects_imbalanced_trial_and_header_mismatch():
    pack = example_pack()
    pack["trial_balance"]["lines"][0]["debit"] = "90.00"
    report = reconcile_books_pack(pack)
    assert not report["reconciled"]
    assert "trial_balance_not_balanced" in report["findings"]
    assert "trial_balance_header_mismatch" in report["findings"]
    assert "account_closing_balance_mismatch:cash" in report["findings"]


def test_detects_ledger_account_omission_and_closing_mismatch():
    pack = example_pack()
    pack["general_ledger"][0]["closing_balance"] = "99.00"
    assert "account_closing_balance_mismatch:cash" in reconcile_books_pack(pack)["findings"]
    pack["general_ledger"].pop()
    assert "ledger_trial_account_mismatch" in reconcile_books_pack(pack)["findings"]


def test_missing_reports_are_not_marked_reconciled():
    assert reconcile_books_pack({}) == {
        "reconciled": False, "findings": ["missing_trial_balance_or_ledger"]
    }


def test_opening_balance_not_compared_to_period_turnover():
    pack = example_pack()
    pack["general_ledger"][0]["opening_balance"] = "900.00"
    pack["general_ledger"][0]["closing_balance"] = "1000.00"
    pack["general_ledger"][1]["opening_balance"] = "900.00"
    pack["general_ledger"][1]["closing_balance"] = "1000.00"
    assert reconcile_books_pack(pack)["reconciled"] is True


def test_gross_debits_and_credits_on_same_account_compare_net_movement():
    pack = example_pack()
    pack["trial_balance"]["lines"][0]["debit"] = "150.00"
    pack["trial_balance"]["lines"][0]["credit"] = "50.00"
    pack["trial_balance"]["lines"][1]["debit"] = "50.00"
    pack["trial_balance"]["lines"][1]["credit"] = "150.00"
    pack["trial_balance"]["total_debit"] = "200.00"
    pack["trial_balance"]["total_credit"] = "200.00"
    assert reconcile_books_pack(pack)["reconciled"] is True
