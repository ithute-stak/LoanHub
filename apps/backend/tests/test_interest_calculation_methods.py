import calendar
from datetime import date
from decimal import Decimal

import pytest

from database.models.enums import LoanCalculationMethod
from services.interest_calculation_service import (
    calculate_daily_accrued_interest,
    calculate_loan_terms,
)


def monthly_test_dates(first_due: date, count: int) -> list[date]:
    """Build fixed test fixtures only; production code never derives installment dates."""
    values: list[date] = []
    for offset in range(count):
        month_index = first_due.month - 1 + offset
        year = first_due.year + month_index // 12
        month = month_index % 12 + 1
        day = min(first_due.day, calendar.monthrange(year, month)[1])
        values.append(date(year, month, day))
    return values


def test_daily_actual_month_matches_spreadsheet_first_period():
    interest, segments = calculate_daily_accrued_interest(
        Decimal("1000"),
        Decimal("36"),
        date(2024, 4, 24),
        date(2024, 5, 24),
    )

    assert interest == Decimal("29.23")
    assert [(row["days"], row["days_in_month"]) for row in segments] == [(6, 30), (24, 31)]
    assert [Decimal(row["interest"]) for row in segments] == [Decimal("6.00"), Decimal("23.23")]


def test_daily_actual_month_matches_spreadsheet_second_period():
    interest, segments = calculate_daily_accrued_interest(
        Decimal("844.78"),
        Decimal("36"),
        date(2024, 5, 24),
        date(2024, 6, 24),
    )

    assert interest == Decimal("25.99")
    assert [(row["days"], row["days_in_month"]) for row in segments] == [(7, 31), (24, 30)]
    assert [Decimal(row["interest"]) for row in segments] == [Decimal("5.72"), Decimal("20.27")]


@pytest.mark.parametrize("method", list(LoanCalculationMethod))
def test_every_method_builds_a_balanced_schedule(method: LoanCalculationMethod):
    monthly, total, details = calculate_loan_terms(
        principal=Decimal("1000"),
        rate_percent=Decimal("36"),
        term_months=6,
        processing_fee=Decimal("75"),
        interest_method=method,
        start_date=date(2024, 4, 24),
        due_dates=monthly_test_dates(date(2024, 5, 24), 6),
    )

    rows = details["schedule_rows"]
    assert len(rows) == 6
    assert monthly == Decimal(rows[0]["total_due"])
    assert total == sum((Decimal(row["total_due"]) for row in rows), Decimal("0"))
    assert sum((Decimal(row["principal_due"]) for row in rows), Decimal("0")) == Decimal("1000.00")
    assert sum((Decimal(row["fee_due"]) for row in rows), Decimal("0")) == Decimal("75.00")
    assert Decimal(rows[-1]["closing_balance"]) == Decimal("0.00")
    assert all(Decimal(row["principal_due"]) >= 0 for row in rows)
    assert all(Decimal(row["interest_due"]) >= 0 for row in rows)


def test_reducing_balance_interest_falls_as_principal_reduces():
    _, _, details = calculate_loan_terms(
        principal=Decimal("1000"),
        rate_percent=Decimal("36"),
        term_months=6,
        interest_method=LoanCalculationMethod.REDUCING_BALANCE,
        start_date=date(2024, 4, 24),
        due_dates=monthly_test_dates(date(2024, 5, 24), 6),
    )
    interests = [Decimal(row["interest_due"]) for row in details["schedule_rows"]]
    assert interests == sorted(interests, reverse=True)
    assert interests[0] > interests[-1]


def test_compound_interest_capitalises_prior_interest():
    _, _, details = calculate_loan_terms(
        principal=Decimal("1000"),
        rate_percent=Decimal("36"),
        term_months=3,
        interest_method=LoanCalculationMethod.COMPOUND_INTEREST,
        start_date=date(2024, 4, 24),
        due_dates=monthly_test_dates(date(2024, 5, 24), 3),
    )
    interests = [Decimal(row["interest_due"]) for row in details["schedule_rows"]]
    assert interests == [Decimal("30.00"), Decimal("30.90"), Decimal("31.83")]


def test_simple_interest_stays_on_original_principal():
    _, total, details = calculate_loan_terms(
        principal=Decimal("1000"),
        rate_percent=Decimal("36"),
        term_months=24,
        interest_method=LoanCalculationMethod.SIMPLE_INTEREST,
        start_date=date(2024, 1, 1),
        due_dates=monthly_test_dates(date(2024, 2, 1), 24),
    )
    assert Decimal(details["total_interest"]) == Decimal("720.00")
    assert total == Decimal("1720.00")


def test_manual_due_dates_are_preserved_exactly():
    manual_dates = [date(2026, 8, 15), date(2026, 9, 30), date(2026, 11, 5)]
    _, _, details = calculate_loan_terms(
        principal=Decimal("1000"),
        rate_percent=Decimal("20"),
        term_months=3,
        interest_method=LoanCalculationMethod.DAILY_ACCRUAL_REDUCING,
        start_date=date(2026, 7, 28),
        due_dates=manual_dates,
    )
    assert [row["due_date"] for row in details["schedule_rows"]] == [value.isoformat() for value in manual_dates]


def test_schedule_rejects_missing_manual_due_dates():
    with pytest.raises(ValueError, match="Enter exactly 3 installment due dates"):
        calculate_loan_terms(
            principal=Decimal("1000"),
            rate_percent=Decimal("20"),
            term_months=3,
            interest_method=LoanCalculationMethod.MICRO_LOAN,
        )
