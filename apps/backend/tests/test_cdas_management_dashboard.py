from __future__ import annotations

from services.cdas_management_dashboard import build_management_dashboard


def _dashboard() -> dict:
    return build_management_dashboard(
        calendar={
            "as_of": "2026-09-15",
            "summary": {"overdue": 3, "today": 2, "next_30_days": 8},
        },
        priorities={
            "summary": {"critical": 2, "high": 4},
        },
        pipeline={
            "summary": {
                "active": 12,
                "booked": 5,
                "active_monthly_deduction_value": 18450.25,
            },
            "stages": [
                {
                    "id": "identified",
                    "label": "Identified",
                    "order": 0,
                    "count": 6,
                    "monthly_deduction_value": 9000,
                    "items": [{"client_name": "Hidden Client"}],
                },
                {
                    "id": "ready_to_book",
                    "label": "Ready to Book",
                    "order": 3,
                    "count": 2,
                    "monthly_deduction_value": 4500,
                    "items": [{"client_reference": "SECRET-REF"}],
                },
            ],
        },
        followups={
            "summary": {
                "unassigned": 4,
                "overdue_follow_ups": 3,
                "scheduled_follow_ups": 5,
                "contacted": 7,
            },
            "items": [{"client_name": "Do Not Leak"}],
        },
        failures={
            "summary": {
                "failure_attempts": 7,
                "currently_failed": 2,
                "retryable": 1,
                "retry_due": 1,
            },
            "reason_counts": [
                {
                    "reason_code": "client_unreachable",
                    "reason_label": "Client unreachable",
                    "count": 3,
                    "reason_details": "private detail",
                }
            ],
            "items": [{"client_reference": "FAIL-SECRET"}],
        },
        quality={
            "summary": {
                "clients_checked": 20,
                "clients_with_issues": 6,
                "blocker_clients": 2,
                "total_issues": 9,
                "blocker_issues": 3,
                "warning_issues": 6,
                "excluded_monthly_amount": 1300,
            },
            "items": [{"nid": "999999999999"}],
        },
        duplicates={
            "summary": {
                "candidate_pairs": 3,
                "high_confidence_pairs": 2,
                "affected_client_profiles": 5,
            },
            "items": [{"employee_no": "EMP-SECRET"}],
        },
        changes={
            "summary": {
                "clients_with_material_changes": 4,
                "material_changes": 7,
            },
            "items": [{"client_name": "Changed Secret"}],
        },
        forecast={
            "as_of": "2026-09-15",
            "summary": {
                "book_now_count": 4,
                "book_now_value": 6200,
                "scheduled_count": 10,
                "scheduled_value": 21000,
                "next_3_months": {"opportunity_count": 5, "monthly_deduction_value": 9700},
                "next_6_months": {"opportunity_count": 7, "monthly_deduction_value": 14200},
                "next_12_months": {"opportunity_count": 10, "monthly_deduction_value": 21000},
                "excluded_quality_count": 2,
                "excluded_quality_value": 1100,
                "unscheduled_count": 1,
                "peak_month": "2026-11",
                "peak_month_value": 7600,
            },
            "months": [
                {
                    "month": "2026-10",
                    "label": "Oct 2026",
                    "opportunity_count": 2,
                    "client_count": 2,
                    "monthly_deduction_value": 4100,
                    "employer_count": 2,
                    "agency_count": 2,
                    "client_name": "Never expose",
                }
            ],
            "top_employers": [
                {
                    "name": "Ministry of Works",
                    "book_now_count": 2,
                    "book_now_value": 3000,
                    "scheduled_count": 3,
                    "scheduled_value": 5000,
                    "total_opportunity_value": 8000,
                }
            ],
            "top_agencies": [
                {
                    "name": "Agency Alpha",
                    "book_now_count": 1,
                    "book_now_value": 2000,
                    "scheduled_count": 4,
                    "scheduled_value": 6000,
                    "total_opportunity_value": 8000,
                }
            ],
        },
    )


def test_management_dashboard_composes_existing_operational_summaries() -> None:
    result = _dashboard()

    assert result["as_of"] == "2026-09-15"
    assert result["operations"] == {
        "active_opportunities": 12,
        "active_monthly_deduction_value": 18450.25,
        "overdue_booking_windows": 3,
        "due_today": 2,
        "next_30_days": 8,
        "critical_priorities": 2,
        "high_priorities": 4,
        "booked_total": 5,
    }
    assert result["workflow"]["unassigned_open"] == 4
    assert result["workflow"]["retry_due"] == 1
    assert result["data_quality"]["duplicate_candidate_pairs"] == 3
    assert result["data_quality"]["material_changes"] == 7
    assert result["forecast"]["next_12_months"]["opportunity_count"] == 10
    assert result["top_employers"][0]["employer"] == "Ministry of Works"
    assert result["top_agencies"][0]["agency"] == "Agency Alpha"


def test_management_dashboard_strips_record_level_identity_and_free_text() -> None:
    result = _dashboard()
    rendered = repr(result)

    for secret in (
        "Hidden Client",
        "SECRET-REF",
        "Do Not Leak",
        "private detail",
        "FAIL-SECRET",
        "999999999999",
        "EMP-SECRET",
        "Changed Secret",
        "Never expose",
    ):
        assert secret not in rendered

    banned_keys = {"client_name", "client_reference", "employee_no", "nid", "notes", "reason_details"}

    def walk(value):
        if isinstance(value, dict):
            assert banned_keys.isdisjoint(value.keys())
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result)


def test_management_dashboard_exposes_controlled_aggregate_breakdowns_only() -> None:
    result = _dashboard()

    assert result["pipeline_stages"] == [
        {
            "id": "identified",
            "label": "Identified",
            "order": 0,
            "count": 6,
            "monthly_deduction_value": 9000.0,
        },
        {
            "id": "ready_to_book",
            "label": "Ready to Book",
            "order": 3,
            "count": 2,
            "monthly_deduction_value": 4500.0,
        },
    ]
    assert result["failure_reasons"] == [
        {
            "reason_code": "client_unreachable",
            "reason_label": "Client unreachable",
            "count": 3,
        }
    ]
    assert result["forecast_months"][0] == {
        "month": "2026-10",
        "label": "Oct 2026",
        "opportunity_count": 2,
        "client_count": 2,
        "monthly_deduction_value": 4100.0,
        "employer_count": 2,
        "agency_count": 2,
    }


def test_management_dashboard_policy_is_explicitly_non_decisional() -> None:
    policy = _dashboard()["policy"]

    assert policy["aggregate_only"] is True
    assert policy["automated_credit_decision"] is False
    assert "does not determine borrower approval" in policy["description"]
    assert "eligibility" in policy["description"]
    assert "loan amount" in policy["description"]
    assert "pricing" in policy["description"]
    assert "disbursement" in policy["description"]
    assert "revenue" in policy["description"]
