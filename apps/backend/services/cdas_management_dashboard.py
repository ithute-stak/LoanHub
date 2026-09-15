from __future__ import annotations

from typing import Any


def _summary(source: dict[str, Any]) -> dict[str, Any]:
    value = source.get("summary") or {}
    return dict(value) if isinstance(value, dict) else {}


def _safe_pipeline_stages(source: dict[str, Any]) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    for stage in source.get("stages") or []:
        stages.append(
            {
                "id": stage.get("id"),
                "label": stage.get("label"),
                "order": int(stage.get("order") or 0),
                "count": int(stage.get("count") or 0),
                "monthly_deduction_value": round(float(stage.get("monthly_deduction_value") or 0), 2),
            }
        )
    return stages


def _safe_failure_reasons(source: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "reason_code": item.get("reason_code"),
            "reason_label": item.get("reason_label"),
            "count": int(item.get("count") or 0),
        }
        for item in source.get("reason_counts") or []
    ]


def _safe_forecast_months(source: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "month": item.get("month"),
            "label": item.get("label"),
            "opportunity_count": int(item.get("opportunity_count") or 0),
            "client_count": int(item.get("client_count") or 0),
            "monthly_deduction_value": round(float(item.get("monthly_deduction_value") or 0), 2),
            "employer_count": int(item.get("employer_count") or 0),
            "agency_count": int(item.get("agency_count") or 0),
        }
        for item in source.get("months") or []
    ]


def _safe_concentrations(values: list[dict[str, Any]] | None, *, key: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in values or []:
        result.append(
            {
                key: item.get(key),
                "book_now_count": int(item.get("book_now_count") or 0),
                "book_now_value": round(float(item.get("book_now_value") or 0), 2),
                "scheduled_count": int(item.get("scheduled_count") or 0),
                "scheduled_value": round(float(item.get("scheduled_value") or 0), 2),
                "total_opportunity_value": round(float(item.get("total_opportunity_value") or 0), 2),
            }
        )
    return result


def build_management_dashboard(
    *,
    calendar: dict[str, Any],
    priorities: dict[str, Any],
    pipeline: dict[str, Any],
    followups: dict[str, Any],
    failures: dict[str, Any],
    quality: dict[str, Any],
    duplicates: dict[str, Any],
    changes: dict[str, Any],
    forecast: dict[str, Any],
) -> dict[str, Any]:
    """Compose existing CDAS operational summaries into a management-safe view.

    The dashboard deliberately contains aggregate workflow information only. It does not
    expose client identity rows and it does not create approval, eligibility, pricing,
    loan-amount, disbursement or revenue predictions.
    """
    calendar_summary = _summary(calendar)
    priority_summary = _summary(priorities)
    pipeline_summary = _summary(pipeline)
    followup_summary = _summary(followups)
    failure_summary = _summary(failures)
    quality_summary = _summary(quality)
    duplicate_summary = _summary(duplicates)
    change_summary = _summary(changes)
    forecast_summary = _summary(forecast)

    return {
        "as_of": calendar.get("as_of") or forecast.get("as_of"),
        "operations": {
            "active_opportunities": int(pipeline_summary.get("active") or 0),
            "active_monthly_deduction_value": round(float(pipeline_summary.get("active_monthly_deduction_value") or 0), 2),
            "overdue_booking_windows": int(calendar_summary.get("overdue") or 0),
            "due_today": int(calendar_summary.get("today") or 0),
            "next_30_days": int(calendar_summary.get("next_30_days") or 0),
            "critical_priorities": int(priority_summary.get("critical") or 0),
            "high_priorities": int(priority_summary.get("high") or 0),
            "booked_total": int(pipeline_summary.get("booked") or 0),
        },
        "workflow": {
            "unassigned_open": int(followup_summary.get("unassigned") or 0),
            "overdue_follow_ups": int(followup_summary.get("overdue_follow_ups") or 0),
            "scheduled_follow_ups": int(followup_summary.get("scheduled_follow_ups") or 0),
            "contacted_open": int(followup_summary.get("contacted") or 0),
            "currently_failed": int(failure_summary.get("currently_failed") or 0),
            "retryable": int(failure_summary.get("retryable") or 0),
            "retry_due": int(failure_summary.get("retry_due") or 0),
            "failure_attempts": int(failure_summary.get("failure_attempts") or 0),
        },
        "data_quality": {
            "profiles_checked": int(quality_summary.get("clients_checked") or 0),
            "profiles_with_issues": int(quality_summary.get("clients_with_issues") or 0),
            "blocker_clients": int(quality_summary.get("blocker_clients") or 0),
            "total_issues": int(quality_summary.get("total_issues") or 0),
            "blocker_issues": int(quality_summary.get("blocker_issues") or 0),
            "warning_issues": int(quality_summary.get("warning_issues") or 0),
            "excluded_monthly_amount": round(float(quality_summary.get("excluded_monthly_amount") or 0), 2),
            "duplicate_candidate_pairs": int(duplicate_summary.get("candidate_pairs") or 0),
            "high_confidence_duplicate_pairs": int(duplicate_summary.get("high_confidence_pairs") or 0),
            "affected_duplicate_profiles": int(duplicate_summary.get("affected_client_profiles") or 0),
            "clients_with_material_changes": int(change_summary.get("clients_with_material_changes") or 0),
            "material_changes": int(change_summary.get("material_changes") or 0),
        },
        "forecast": {
            "book_now_count": int(forecast_summary.get("book_now_count") or 0),
            "book_now_value": round(float(forecast_summary.get("book_now_value") or 0), 2),
            "scheduled_count": int(forecast_summary.get("scheduled_count") or 0),
            "scheduled_value": round(float(forecast_summary.get("scheduled_value") or 0), 2),
            "next_3_months": dict(forecast_summary.get("next_3_months") or {}),
            "next_6_months": dict(forecast_summary.get("next_6_months") or {}),
            "next_12_months": dict(forecast_summary.get("next_12_months") or {}),
            "excluded_quality_count": int(forecast_summary.get("excluded_quality_count") or 0),
            "excluded_quality_value": round(float(forecast_summary.get("excluded_quality_value") or 0), 2),
            "unscheduled_count": int(forecast_summary.get("unscheduled_count") or 0),
            "peak_month": forecast_summary.get("peak_month"),
            "peak_month_value": round(float(forecast_summary.get("peak_month_value") or 0), 2),
        },
        "pipeline_stages": _safe_pipeline_stages(pipeline),
        "failure_reasons": _safe_failure_reasons(failures),
        "forecast_months": _safe_forecast_months(forecast),
        "top_employers": _safe_concentrations(forecast.get("top_employers"), key="employer"),
        "top_agencies": _safe_concentrations(forecast.get("top_agencies"), key="agency"),
        "policy": {
            "aggregate_only": True,
            "automated_credit_decision": False,
            "description": "Operational management intelligence only. This dashboard does not determine borrower approval, eligibility, loan amount, pricing, disbursement or revenue.",
        },
    }
