from decimal import Decimal

from services.loan_sequence_history import recorded_loan_changes, recorded_balance_impact


def test_recorded_balance_and_rate_changes():
    changes = recorded_loan_changes(
        {"balance": "1800.00", "interest_rate": "20.000"},
        {"balance": "1610.00", "interest_rate": "15.000"},
    )
    assert changes == [
        {"field": "balance", "before_recorded": True, "after_recorded": True,
         "before": "1800.00", "after": "1610.00"},
        {"field": "interest_rate", "before_recorded": True, "after_recorded": True,
         "before": "20.000", "after": "15.000"},
    ]


def test_missing_null_and_zero_are_distinct():
    changes = recorded_loan_changes({"maturity_date": None}, {"balance": 0})
    assert changes == [
        {"field": "balance", "before_recorded": False, "after_recorded": True,
         "before": None, "after": "0"},
        {"field": "maturity_date", "before_recorded": True, "after_recorded": False,
         "before": None, "after": None},
    ]


def test_equal_decimal_values_not_reported():
    assert recorded_loan_changes({"balance": "100.00"}, {"balance": 100}) == []


def test_sensitive_and_untrusted_values_excluded():
    assert recorded_loan_changes(
        {"bank_account_number": "123456789", "password": "secret",
         "balance": {"nested": "secret"}, "status": "invalid status with spaces"},
        {"bank_account_number": "987654321", "password": "other",
         "balance": "0", "status": "active"},
    ) == []


def test_invalid_numeric_values_excluded():
    for value in (True, "NaN", "Infinity", "1e100", [], "9" * 100):
        assert recorded_loan_changes({"balance": value}, {"balance": "0"}) == []


def test_dates_and_installment_period():
    changes = recorded_loan_changes(
        {"maturity_date": "2026-12-25", "repayment_period": 3},
        {"maturity_date": "2027-01-25", "repayment_period": 4},
    )
    assert [change["field"] for change in changes] == ["maturity_date", "repayment_period"]


def test_non_dict_snapshots_are_safe():
    assert recorded_loan_changes([], "invalid") == []


def test_balance_impact_exact_and_directional():
    for old, new, delta in (("1800.00", "1200.00", "-600.00"),
                            ("1200.00", "1800.00", "600.00"),
                            ("0.10", "0.30", "0.20"),
                            ("0", "0.00", "0.00")):
        assert recorded_balance_impact({"balance": old}, {"balance": new}, "success") == {
            "evidence": "recorded_loan_balance", "before": format(Decimal(old), ".2f"),
            "after": format(Decimal(new), ".2f"), "delta": delta}


def test_balance_impact_missing_or_invalid():
    for snapshot in ({}, {"balance": None}, {"balance": "NaN"}, {"balance": "1.001"}, {"balance": "10000000000000"}):
        assert recorded_balance_impact(snapshot, {"balance": "0"}, "success") == {
            "evidence": "not_recorded", "before": None, "after": None, "delta": None}


def test_balance_impact_failed_event():
    assert recorded_balance_impact({"balance": 600}, {"balance": 0}, "failed") == {
        "evidence": "not_confirmed", "before": None, "after": None, "delta": None}
