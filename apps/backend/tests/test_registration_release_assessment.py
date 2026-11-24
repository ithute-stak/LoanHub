"""Phase 89: report and approvals cannot self-enable production registration."""
from services.registration_release_assessment import (
    REQUIRED_APPROVALS,
    REQUIRED_CERTIFICATIONS,
    assess_registration_release,
)


def report(**updates):
    data = {
        "legacy_cross_source_audit_complete": True,
        "legacy_cross_source_counts": {
            "national_id_overlap_groups": 0,
            "passport_overlap_groups": 0,
            "repeated_legacy_passport_groups": 0,
        },
        "legacy_linkage_review_complete": True,
        "legacy_linkage_review": {
            "matching_identity_groups": 0,
            "unresolved_identity_groups": 0,
        },
        "operator_review_candidate": True,
        "safe_to_execute": False,
        "production_approved": False,
        "registration_enabled": False,
    }
    data.update(updates)
    return data


def all_true(keys):
    return {key: True for key in keys}


def assess(audit=None, *, approvals=None, certifications=None):
    return assess_registration_release(
        audit_report=report() if audit is None else audit,
        approvals=all_true(REQUIRED_APPROVALS) if approvals is None else approvals,
        certifications=(
            all_true(REQUIRED_CERTIFICATIONS)
            if certifications is None else certifications
        ),
    )


def test_complete_checklist_still_cannot_activate_registration_or_migration():
    outcome = assess()
    assert outcome.reviewable is True
    assert outcome.registration_enabled is False
    assert outcome.authorization_to_deploy is False
    assert outcome.automatic_migration_allowed is False


def test_missing_any_independent_approval_blocks_review():
    for key in REQUIRED_APPROVALS:
        approvals = all_true(REQUIRED_APPROVALS)
        approvals[key] = False
        outcome = assess(approvals=approvals)
        assert outcome.reviewable is False
        assert key in outcome.missing_approvals


def test_missing_any_certification_blocks_review():
    for key in REQUIRED_CERTIFICATIONS:
        certs = all_true(REQUIRED_CERTIFICATIONS)
        certs[key] = False
        outcome = assess(certifications=certs)
        assert outcome.reviewable is False
        assert key in outcome.missing_certifications


def test_historical_passport_collision_blocks_review():
    audit = report(legacy_cross_source_counts={
        "national_id_overlap_groups": 0,
        "passport_overlap_groups": 1,
        "repeated_legacy_passport_groups": 0,
    })
    result = assess(audit)
    assert result.reviewable is False
    assert result.pending_data_review is True


def test_missing_audit_and_forged_enabling_fields_fail_closed():
    assert assess({}).reviewable is False
    assert assess(report(registration_enabled=True)).reviewable is False
    assert assess(report(production_approved=True)).reviewable is False
    assert assess(report(safe_to_execute=True)).reviewable is False
    assert assess(report(legacy_cross_source_audit_complete=False)).reviewable is False


def test_boolean_and_malformed_historical_counts_not_trusted():
    for count in (True, None, -1, "0"):
        audit = report(legacy_cross_source_counts={
            "national_id_overlap_groups": count,
            "passport_overlap_groups": 0,
            "repeated_legacy_passport_groups": 0,
        })
        result = assess(audit)
        assert result.reviewable is False
        assert result.pending_data_review is True


def test_unverified_linkage_triage_cannot_be_bypassed_by_approvals():
    for audit in (
        report(legacy_linkage_review_complete=False),
        report(legacy_linkage_review=None),
        report(legacy_linkage_review={
            "matching_identity_groups": 0,
            "unresolved_identity_groups": 1,
        }),
        report(legacy_linkage_review={
            "matching_identity_groups": True,
            "unresolved_identity_groups": 0,
        }),
        report(legacy_linkage_review={
            "matching_identity_groups": 1,
            "unresolved_identity_groups": 0,
        }),
    ):
        outcome = assess(audit)
        assert outcome.reviewable is False
        assert outcome.pending_data_review is True
        assert outcome.registration_enabled is False
        assert outcome.authorization_to_deploy is False
