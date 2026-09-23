from datetime import date, datetime
from types import SimpleNamespace
from uuid import UUID

from services.cdas_dashboard_kpis import (
    month_bounds,
    movement,
    run_rate_for_period,
    shift_month,
    summarize_active_book,
)


BRANCH_A = UUID("11111111-1111-1111-1111-111111111111")
BRANCH_B = UUID("22222222-2222-2222-2222-222222222222")
OFFICER_A = UUID("33333333-3333-3333-3333-333333333333")
OFFICER_B = UUID("44444444-4444-4444-4444-444444444444")
BORROWER_A = UUID("55555555-5555-5555-5555-555555555555")
BORROWER_B = UUID("66666666-6666-6666-6666-666666666666")
BORROWER_C = UUID("77777777-7777-7777-7777-777777777777")


def _state(*, lifecycle="active", settled_at=None, cancelled_at=None):
    return SimpleNamespace(
        lifecycle_status=lifecycle,
        settled_at=settled_at,
        cancelled_at=cancelled_at,
    )


def _mandate(
    *,
    amount=500,
    start=date(2026, 1, 1),
    end=None,
    activated=datetime(2026, 1, 1),
    completed=None,
    branch_id=BRANCH_A,
    officer_id=OFFICER_A,
    borrower_id=BORROWER_A,
):
    return SimpleNamespace(
        monthly_deduction=amount,
        start_date=start,
        end_date=end,
        activated_at=activated,
        completed_at=completed,
        branch_id=branch_id,
        created_by_user_id=officer_id,
        borrower_id=borrower_id,
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


def test_active_book_summary_ranks_branches_and_officers_by_monthly_value():
    rows = [
        (_state(), _mandate(amount=500, branch_id=BRANCH_A, officer_id=OFFICER_A, borrower_id=BORROWER_A)),
        (_state(), _mandate(amount=400, branch_id=BRANCH_A, officer_id=OFFICER_A, borrower_id=BORROWER_B)),
        (_state(), _mandate(amount=1200, branch_id=BRANCH_B, officer_id=OFFICER_B, borrower_id=BORROWER_C)),
    ]

    summary = summarize_active_book(
        rows,
        branch_names={BRANCH_A: "Maseru", BRANCH_B: "Leribe"},
        officer_names={OFFICER_A: "Officer A", OFFICER_B: "Officer B"},
    )

    assert summary["branches"][0] == {
        "branch_id": str(BRANCH_B),
        "name": "Leribe",
        "active_deduction_count": 1,
        "active_client_count": 1,
        "monthly_amount": 1200.0,
    }
    assert summary["branches"][1]["monthly_amount"] == 900.0
    assert summary["branches"][1]["active_client_count"] == 2
    assert summary["officers"][0]["name"] == "Officer B"
    assert summary["officers"][1]["active_deduction_count"] == 2


def test_active_book_summary_keeps_unassigned_branch_but_not_unattributed_officer():
    rows = [
        (_state(), _mandate(amount=250, branch_id=None, officer_id=None, borrower_id=BORROWER_A)),
    ]

    summary = summarize_active_book(rows)

    assert summary["branches"][0]["name"] == "Unassigned branch"
    assert summary["branches"][0]["monthly_amount"] == 250.0
    assert summary["officers"] == []
