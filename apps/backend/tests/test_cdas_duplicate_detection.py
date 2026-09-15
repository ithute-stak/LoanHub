from __future__ import annotations

from services.cdas_duplicate_detection import build_duplicate_detection


def _profile(key: str, **values):
    return {
        "client_key": key,
        "client_name": values.get("client_name"),
        "client_reference": values.get("client_reference"),
        "employee_no": values.get("employee_no"),
        "nid": values.get("nid"),
        "employer": values.get("employer"),
        "current_agency_name": values.get("current_agency_name"),
        "latest_analysis_id": values.get("latest_analysis_id"),
        "latest_analyzed_at": values.get("latest_analyzed_at"),
        "analysis_count": values.get("analysis_count", 1),
        "opportunity_count": values.get("opportunity_count", 0),
    }


def test_shared_strong_identifier_is_high_confidence() -> None:
    result = build_duplicate_detection([
        _profile("a", client_name="Mpho Test", employee_no=" 00123 ", employer="Employer A"),
        _profile("b", client_name="M. Test", client_reference="00123", employer="Employer B"),
    ])

    assert result["total"] == 1
    candidate = result["items"][0]
    assert candidate["confidence"] == "HIGH"
    assert "SHARED_STRONG_IDENTIFIER" in candidate["reason_codes"]
    assert candidate["shared_identifiers"][0]["value"] == "00123"


def test_exact_name_and_employer_is_high_confidence_case_insensitively() -> None:
    result = build_duplicate_detection([
        _profile("a", client_name="  Lerato   Mokoena ", client_reference="A-1", employer="Ministry Of Health"),
        _profile("b", client_name="lerato mokoena", client_reference="B-2", employer=" ministry of health "),
    ])

    assert result["total"] == 1
    assert result["items"][0]["confidence"] == "HIGH"
    assert "SAME_NAME_AND_EMPLOYER" in result["items"][0]["reason_codes"]


def test_exact_name_with_incomplete_identity_is_medium_confidence_review_only() -> None:
    result = build_duplicate_detection([
        _profile("a", client_name="Thabo Molefe", employee_no="EMP-9", employer="Employer A"),
        _profile("b", client_name=" thabo   molefe ", employer=None),
    ])

    assert result["total"] == 1
    assert result["items"][0]["confidence"] == "MEDIUM"
    assert result["items"][0]["reason_codes"] == ["SAME_NAME_INCOMPLETE_IDENTITY"]
    assert result["policy"]["automatic_merge"] is False
    assert result["policy"]["fuzzy_name_matching"] is False


def test_same_name_with_complete_conflicting_identities_is_not_flagged() -> None:
    result = build_duplicate_detection([
        _profile("a", client_name="Neo Mokoena", employee_no="EMP-1", employer="Employer A"),
        _profile("b", client_name="Neo Mokoena", employee_no="EMP-2", employer="Employer B"),
    ])

    assert result["total"] == 0
    assert result["summary"]["affected_client_profiles"] == 0


def test_similar_but_not_exact_names_are_not_fuzzy_matched() -> None:
    result = build_duplicate_detection([
        _profile("a", client_name="Maseko Thabo", employer=None),
        _profile("b", client_name="Maseko Thaboho", employer=None),
    ])

    assert result["total"] == 0


def test_summary_counts_candidate_pairs_and_unique_affected_profiles() -> None:
    result = build_duplicate_detection([
        _profile("a", client_name="A Person", employee_no="111", employer="One"),
        _profile("b", client_name="B Person", employee_no="111", employer="Two"),
        _profile("c", client_name="C Person", nid="999", employer="Three"),
        _profile("d", client_name="C Person", nid="999", employer="Four"),
    ])

    assert result["summary"] == {
        "profiles_checked": 4,
        "candidate_pairs": 2,
        "high_confidence_pairs": 2,
        "medium_confidence_pairs": 0,
        "affected_client_profiles": 4,
    }
