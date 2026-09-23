from datetime import date, datetime
from types import SimpleNamespace

from services.cdas_dashboard_kpis import month_bounds, movement, run_rate_for_period, shift_month


def _state(*, lifecycle="active", settled_at=None, cancelled_at=None):
    return SimpleNamespace(
        lifecycle_status=lifecycle,
        settled_at=settled_at,
        cancelled_at=cancelled_at,
    )


def _mandate(*, amount=500, start=date(2026, 1, 1), end=None, activated=datetime(2026, 1, 1), completed=None):
    return SimpleNamespace(
        monthly_deduction=amount,
        start_date=start,
        end_date=end,
        activated_at=activated,
        completed_at=completed,
    )


def test_month_bounds_and_shift_handle_year_rollover():
    assert month_bounds(date(2026, 12, 20)) == (date(2026, 12, 1), date(2026, 12, 31))
    assert shift_month(date(2026, 12, 1), 1) == date(2027, 1, 1)
    assert shift_month(date(2026, 1, 1), -1) == date(2025, 12, 1)


def test_movement_reports_growth_decay_stable_and_new_book():
    assert movement(1200, 1000)["direction"] == "growth"
    assert movement(800, 1000)["direction"] == "decay"
    assert movement(1000, 1000)["direction"] == "stable"
    created = movement(500, 0)
    assert created["direction"] == "new_book"
    assert created["percent"] is None


def test_run_rate_uses_activation_and_completion_dates():
    rows = [
        (_state(), _mandate(amount=500, activated=datetime(2026, 1, 10))),
        (
            _state(settled_at=datetime(2026, 2, 15)),
            _mandate(amount=300, activated=datetime(2026, 1, 1), completed=datetime(2026, 2, 15)),
        ),
        (_state(), _mandate(amount=900, start=date(2026, 3, 1), activated=datetime(2026, 3, 1))),
    ]

    assert run_rate_for_period(rows, date(2026, 1, 1), date(2026, 1, 31)) == 800
    assert run_rate_for_period(rows, date(2026, 2, 1), date(2026, 2, 28)) == 800
    assert run_rate_for_period(rows, date(2026, 3, 1), date(2026, 3, 31)) == 1400


def test_run_rate_excludes_not_yet_activated_mandate():
    rows = [(_state(lifecycle="approved"), _mandate(amount=700, activated=None))]
    assert run_rate_for_period(rows, date(2026, 1, 1), date(2026, 1, 31)) == 0
