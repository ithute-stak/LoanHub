from services.cdas_data_quality import build_data_quality_centre, inspect_profile_quality


def _profile(**overrides):
    value = {
        "client_key": "cdas-client-1",
        "client_name": "Test Client",
        "client_reference": "CLIENT-1",
        "employee_no": "EMP-1",
        "nid": "NID-1",
        "employer": "Example Employer",
        "current_agency_name": "Example Agency",
        "current_agency_code": "2561",
        "decision": "WAIT_UNTIL",
        "assessed_available_amount": 900.0,
        "latest_analysis_id": "analysis-1",
        "latest_analyzed_at": "2026-09-15T06:00:00",
        "current_deductions": [
            {
                "item_code": "2561",
                "agency_name": "Example Agency",
                "reference_no": "REF-1",
                "deduction_amount": 500.0,
                "effective_date": "2026-01-01",
                "expiry_date": "2027-01-01",
                "status": "Active",
                "reported_active": True,
                "excluded_from_booking": False,
                "data_quality_status": "OK",
                "data_quality_message": None,
            }
        ],
    }
    value.update(overrides)
    return value


def test_clean_latest_profile_scores_100():
    result = build_data_quality_centre([_profile()])

    assert result["summary"]["clients_checked"] == 1
    assert result["summary"]["clients_with_issues"] == 0
    assert result["summary"]["blocker_clients"] == 0
    assert result["items"][0]["quality_score"] == 100
    assert result["items"][0]["issues"] == []


def test_missing_expiry_is_blocker_and_counts_affected_monthly_value():
    profile = _profile(current_deductions=[
        {
            "item_code": "2595",
            "agency_name": "Competitor Bank",
            "reference_no": "LOAN-99",
            "deduction_amount": 1250.50,
            "effective_date": "2026-03-01",
            "expiry_date": None,
            "status": "Active",
            "reported_active": True,
            "excluded_from_booking": True,
            "data_quality_status": "MISSING_EXPIRY",
            "data_quality_message": "Expiry month is missing.",
        }
    ])
    result = build_data_quality_centre([profile])
    item = result["items"][0]

    assert item["blocker_count"] == 1
    assert item["excluded_monthly_amount"] == 1250.50
    assert result["summary"]["excluded_monthly_amount"] == 1250.50
    assert item["issues"][0]["category"] == "MISSING_EXPIRY"
    assert item["issues"][0]["deduction"]["reference_no"] == "LOAN-99"


def test_date_conflict_and_review_required_are_both_blockers():
    profile = _profile(
        decision="REVIEW_REQUIRED",
        current_deductions=[
            {
                "item_code": "2595",
                "agency_name": "Competitor Bank",
                "reference_no": "LOAN-100",
                "deduction_amount": 700.0,
                "effective_date": "2027-01-01",
                "expiry_date": "2026-12-01",
                "status": "Active",
                "reported_active": True,
                "excluded_from_booking": True,
                "data_quality_status": "DATE_CONFLICT",
                "data_quality_message": "Effective date is after expiry.",
            }
        ],
    )
    issues = inspect_profile_quality(profile)
    categories = {issue["category"] for issue in issues}

    assert "REVIEW_REQUIRED" in categories
    assert "DATE_CONFLICT" in categories
    assert sum(1 for issue in issues if issue["severity"] == "BLOCKER") == 2


def test_missing_profile_fields_are_warnings_not_blockers():
    profile = _profile(
        client_name=None,
        client_reference=None,
        employee_no=None,
        nid=None,
        employer=None,
        current_agency_name=None,
        current_agency_code=None,
        assessed_available_amount=None,
        current_deductions=[],
    )
    issues = inspect_profile_quality(profile)

    assert issues
    assert all(issue["severity"] == "WARNING" for issue in issues)
    assert {issue["category"] for issue in issues} >= {
        "MISSING_CLIENT_NAME",
        "MISSING_STRONG_IDENTIFIER",
        "MISSING_EMPLOYER",
        "MISSING_CDAS_AGENCY",
        "CAPACITY_UNKNOWN",
    }


def test_active_missing_reference_and_invalid_amount_are_warnings():
    profile = _profile(current_deductions=[
        {
            "item_code": "2595",
            "agency_name": "Competitor Bank",
            "reference_no": "",
            "deduction_amount": 0,
            "effective_date": "2026-01-01",
            "expiry_date": "2027-01-01",
            "status": "Active",
            "reported_active": True,
            "excluded_from_booking": False,
            "data_quality_status": "OK",
        }
    ])
    issues = inspect_profile_quality(profile)
    categories = {issue["category"] for issue in issues}

    assert "MISSING_DEDUCTION_REFERENCE" in categories
    assert "INVALID_DEDUCTION_AMOUNT" in categories
    assert all(issue["severity"] == "WARNING" for issue in issues)


def test_blocker_clients_sort_before_warning_and_clean_clients():
    clean = _profile(client_key="clean", client_name="Clean Client")
    warning = _profile(client_key="warning", client_name=None)
    blocker = _profile(
        client_key="blocker",
        client_name="Blocked Client",
        decision="REVIEW_REQUIRED",
    )

    result = build_data_quality_centre([clean, warning, blocker])

    assert [item["client_key"] for item in result["items"]] == ["blocker", "warning", "clean"]
