from __future__ import annotations

from datetime import date

from services.cdas_advanced_search import enrich_opportunity, filter_analyses, filter_opportunities


def test_analysis_filters_combine_identity_quality_dates_and_capacity() -> None:
    items = [
        {
            "id": "a1",
            "client_name": "Mpho Molefe",
            "client_reference": "EMP-100",
            "employee_no": "100",
            "nid": "NID-100",
            "employer": "Ministry of Health",
            "current_agency_name": "First National Bank",
            "decision": "WAIT_UNTIL",
            "assessed_available_amount": 850.0,
            "next_possible_booking_date": "2026-11-01",
            "data_quality_issue_count": 0,
            "analyzed_at": "2026-09-15T10:00:00",
        },
        {
            "id": "a2",
            "client_name": "Other Client",
            "employer": "Other Employer",
            "current_agency_name": "Other Agency",
            "decision": "REVIEW_REQUIRED",
            "assessed_available_amount": 100.0,
            "next_possible_booking_date": "2027-01-01",
            "data_quality_issue_count": 2,
            "analyzed_at": "2026-08-01T10:00:00",
        },
    ]

    result = filter_analyses(
        items,
        query="mpho",
        employer="ministry",
        agency="national",
        decision="wait_until",
        quality="clean",
        booking_from=date(2026, 10, 1),
        booking_to=date(2026, 12, 31),
        analyzed_from=date(2026, 9, 1),
        min_capacity=800,
        max_capacity=900,
    )

    assert [item["id"] for item in result] == ["a1"]


def test_opportunity_filters_assignment_state_ranges_and_quality() -> None:
    source = {
        "id": "o1",
        "client_name": "Mpho Molefe",
        "client_reference": "EMP-100",
        "state": "BOOK_NOW",
        "pipeline_stage": "contact_client",
        "assigned_to_user_id": "user-1",
        "booking_open_date": "2026-09-15",
        "opportunity_agency_name": "Competitor Finance",
        "opportunity_item_code": "2561",
        "opportunity_reference_no": "REF-1",
        "opportunity_deduction_amount": 1200,
        "analysis_snapshot": {
            "profile": {"employer": "Ministry of Health"},
            "decision": "BOOK_NOW",
            "capacity": {"assessed_available_amount": 1500},
            "data_quality_issue_count": 0,
        },
    }
    item = enrich_opportunity(source, assigned_name="Officer One")

    result = filter_opportunities(
        [item],
        query="officer one",
        employer="health",
        agency="competitor",
        decision="book_now",
        state="book_now",
        pipeline_stage="contact_client",
        assigned_to_user_id="user-1",
        quality="clean",
        booking_from=date(2026, 9, 1),
        booking_to=date(2026, 9, 30),
        min_capacity=1400,
        max_capacity=1600,
        min_deduction=1000,
        max_deduction=1300,
    )

    assert len(result) == 1
    assert result[0]["employer"] == "Ministry of Health"
    assert result[0]["assigned_to_name"] == "Officer One"


def test_unassigned_filter_excludes_assigned_opportunities() -> None:
    assigned = {"id": "1", "assigned_to_user_id": "user-1"}
    unassigned = {"id": "2", "assigned_to_user_id": None}

    result = filter_opportunities([assigned, unassigned], assigned_to_user_id="unassigned")

    assert [item["id"] for item in result] == ["2"]


def test_issue_filter_requires_positive_quality_issue_count() -> None:
    items = [
        {"id": "clean", "data_quality_issue_count": 0},
        {"id": "bad", "data_quality_issue_count": 1},
    ]

    assert [item["id"] for item in filter_analyses(items, quality="issues")] == ["bad"]
    assert [item["id"] for item in filter_analyses(items, quality="clean")] == ["clean"]
