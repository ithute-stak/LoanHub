from datetime import date, datetime
from zoneinfo import ZoneInfo

from services.cdas_collection_policy import build_cdas_collection_plan, cdas_payroll_timing


MASERU = ZoneInfo("Africa/Maseru")


def test_after_monthly_window_uses_next_provider_window_and_following_payroll_month():
    timing = cdas_payroll_timing(datetime(2026, 9, 24, 10, 0, tzinfo=MASERU))

    assert timing["processing_window_start"] == "2026-10-14"
    assert timing["processing_window_end"] == "2026-10-20"
    assert timing["processing_time"] == "06:00"
    assert timing["timezone"] == "Africa/Maseru"
    assert timing["effective_month"] == "2026-11"
    assert timing["first_expected_collection_month"] == "2026-11"


def test_before_monthly_window_uses_current_month_window():
    timing = cdas_payroll_timing(datetime(2026, 9, 10, 12, 0, tzinfo=MASERU))

    assert timing["processing_window_start"] == "2026-09-14"
    assert timing["processing_window_end"] == "2026-09-20"
    assert timing["effective_month"] == "2026-10"


def test_after_final_processing_hour_moves_to_next_month_window():
    timing = cdas_payroll_timing(datetime(2026, 9, 20, 7, 0, tzinfo=MASERU))

    assert timing["processing_window_start"] == "2026-10-14"
    assert timing["effective_month"] == "2026-11"


def test_during_final_processing_hour_keeps_current_month_window():
    timing = cdas_payroll_timing(datetime(2026, 9, 20, 6, 59, tzinfo=MASERU))

    assert timing["processing_window_start"] == "2026-09-14"
    assert timing["effective_month"] == "2026-10"


def test_collection_plan_records_selection_and_timing_check_separately():
    selected_at = datetime(2026, 9, 24, 10, 0, tzinfo=MASERU)
    plan = build_cdas_collection_plan(
        enabled=True,
        installment_due_dates=[date(2026, 9, 30), date(2026, 10, 30)],
        term_count=2,
        selected_by_user_id=None,
        selected_at=selected_at,
    )

    assert plan["selected_at"] == selected_at.isoformat()
    assert plan["timing_checked_at"] == selected_at.isoformat()
    assert plan["effective_month"] == "2026-11"
    assert plan["first_expected_collection_month"] == "2026-11"
