from uuid import uuid4

from services.cdas_analysis_history import (
    _record_values,
    analysis_fingerprint,
    sanitize_analysis_snapshot,
)


def _analysis() -> dict:
    return {
        "as_of": "2026-09-14",
        "decision": "BOOK_NOW",
        "next_possible_booking_date": "2026-09-14",
        "profile": {
            "employee_no": "EMP-100",
            "full_name": "Test Client",
            "nid": "123456789012",
            "employer": "Test Employer",
        },
        "application_context": {
            "current_cdas_agency_code": "2966",
            "current_cdas_agency_name": "Lelefa Debt Collection",
        },
        "capacity": {
            "assessed_available_amount": 500.0,
            "booking_allowed": True,
        },
        "booking_term": {
            "amount_owing": 4600.0,
            "months_required": 10,
        },
        "reported_active_monthly_deductions": 2171.0,
        "total_monthly_deductions": 2061.0,
        "data_quality_issue_count": 1,
        "deductions": [
            {
                "item_code": "2907",
                "agency_name": "EXPRESS CREDIT",
                "deduction_amount": 1463.0,
            }
        ],
    }


def test_history_snapshot_recursively_removes_raw_cdas_text():
    analysis = _analysis()
    analysis["raw_text"] = "SECRET SOURCE TEXT"
    analysis["nested"] = {
        "raw-text": "SHOULD ALSO BE REMOVED",
        "safe": "keep me",
        "deeper": [{"source raw text": "REMOVE", "value": 7}],
    }

    cleaned = sanitize_analysis_snapshot(analysis)

    assert "raw_text" not in cleaned
    assert "raw-text" not in cleaned["nested"]
    assert "source raw text" not in cleaned["nested"]["deeper"][0]
    assert cleaned["nested"]["safe"] == "keep me"
    assert cleaned["nested"]["deeper"][0]["value"] == 7


def test_history_fingerprint_deduplicates_same_analysis_but_versions_changes():
    first = _analysis()
    first["raw_text"] = "FIRST CLIPBOARD COPY"
    second = _analysis()
    second["raw_text"] = "SAME ANALYSIS, DIFFERENT SOURCE COPY"

    same_one = analysis_fingerprint(first, client_name="Test Client", client_reference="EMP-100")
    same_two = analysis_fingerprint(second, client_name="Test Client", client_reference="EMP-100")
    assert same_one == same_two

    changed = _analysis()
    changed["capacity"]["assessed_available_amount"] = 650.0
    changed_fingerprint = analysis_fingerprint(changed, client_name="Test Client", client_reference="EMP-100")
    assert changed_fingerprint != same_one


def test_history_record_summary_is_derived_from_structured_analysis_only():
    analysis = _analysis()
    analysis["raw_text"] = "DO NOT STORE THIS"

    values = _record_values(
        company_id=uuid4(),
        analyzed_by_user_id=uuid4(),
        analyzed_by_name="Company Owner",
        analyzed_by_role="company_owner",
        client_name=None,
        client_reference=None,
        analysis=analysis,
    )

    assert values["client_name"] == "Test Client"
    assert values["client_reference"] == "EMP-100"
    assert values["employee_no"] == "EMP-100"
    assert values["employer"] == "Test Employer"
    assert values["current_agency_code"] == "2966"
    assert values["decision"] == "BOOK_NOW"
    assert float(values["assessed_available_amount"]) == 500.0
    assert float(values["amount_owing"]) == 4600.0
    assert values["booking_months"] == 10
    assert values["data_quality_issue_count"] == 1
    assert "raw_text" not in values["analysis_snapshot"]
