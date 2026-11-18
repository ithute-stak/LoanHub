import pytest

from services.assisted_registration_review import decide_registration_review


def test_clear_check_is_not_permission_to_register():
    decision = decide_registration_review(
        identity_match_found=False,
        legacy_capture_count=0,
        already_company_client=False,
        has_existing_loans=False,
    )
    assert decision.decision == "new_identity_candidate"
    assert decision.requires_human_review is True
    assert decision.can_commit is False


@pytest.mark.parametrize("changes", [
    {"identity_match_found": True},
    {"legacy_capture_count": 1},
    {"already_company_client": True},
    {"has_existing_loans": True},
])
def test_existing_records_always_trigger_manual_review(changes):
    kwargs = {
        "identity_match_found": False,
        "legacy_capture_count": 0,
        "already_company_client": False,
        "has_existing_loans": False,
    }
    kwargs.update(changes)
    decision = decide_registration_review(**kwargs)
    assert decision.decision == "manual_review_required"
    assert decision.can_commit is False


@pytest.mark.parametrize("changes", [
    {"legacy_capture_count": -1},
    {"legacy_capture_count": True},
    {"identity_match_found": "false"},
    {"has_existing_loans": 1},
])
def test_invalid_evidence_fails_closed(changes):
    kwargs = {
        "identity_match_found": False,
        "legacy_capture_count": 0,
        "already_company_client": False,
        "has_existing_loans": False,
    }
    kwargs.update(changes)
    with pytest.raises(ValueError):
        decide_registration_review(**kwargs)
