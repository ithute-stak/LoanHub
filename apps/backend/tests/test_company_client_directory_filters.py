from datetime import date

from routers.company_clients import _next_salary_pay_date


def test_salary_day_of_month_rolls_to_next_occurrence():
    assert _next_salary_pay_date("25", date(2026, 7, 20)) == date(2026, 7, 25)
    assert _next_salary_pay_date("25th", date(2026, 7, 29)) == date(2026, 8, 25)


def test_salary_date_clamps_to_end_of_short_month():
    assert _next_salary_pay_date("31", date(2026, 2, 1)) == date(2026, 2, 28)


def test_future_iso_salary_date_is_preserved():
    assert _next_salary_pay_date("2026-08-03", date(2026, 7, 29)) == date(2026, 8, 3)


def test_invalid_salary_date_is_not_invented():
    assert _next_salary_pay_date("end of month", date(2026, 7, 29)) is None
