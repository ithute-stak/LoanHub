"""Phase 89: non-activating checklist for Batlokoa new-client rollout.

Consumes only approved aggregate reports and operator attestations. It is
deliberately NOT a feature flag and has no code path to enable registration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


REQUIRED_APPROVALS = (
    "database_owner",
    "identity_data_steward",
    "security_reviewer",
    "loanhub_operations",
    "batlokoa_business_owner",
)
REQUIRED_CERTIFICATIONS = (
    "normalized_index_ddl_verified",
    "all_identity_writers_reviewed",
    "full_registration_postgres_passed",
    "bank_encryption_and_key_management_reviewed",
    "external_debt_semantics_reviewed",
    "staff_branch_authorization_reviewed",
    "production_rollback_rehearsed",
)


@dataclass(frozen=True)
class RegistrationReleaseAssessment:
    reviewable: bool
    missing_approvals: tuple[str, ...]
    missing_certifications: tuple[str, ...]
    pending_data_review: bool
    registration_enabled: bool = False
    authorization_to_deploy: bool = False
    automatic_migration_allowed: bool = False


def assess_registration_release(
    *,
    audit_report: Mapping[str, object] | None,
    approvals: Mapping[str, bool],
    certifications: Mapping[str, bool],
) -> RegistrationReleaseAssessment:
    """Assess documentation completeness without granting operational access.

    No role-supplied boolean can authorize deployment; independent approval,
    index installation and actual runtime feature activation occur elsewhere.
    The actual database is never queried or modified by this function.
    """
    if not isinstance(approvals, Mapping) or not isinstance(certifications, Mapping):
        raise ValueError("Explicit independent approval and certification maps required")
    missing_approvals = tuple(
        key for key in REQUIRED_APPROVALS if approvals.get(key) is not True
    )
    missing_certifications = tuple(
        key for key in REQUIRED_CERTIFICATIONS
        if certifications.get(key) is not True
    )
    report = audit_report if isinstance(audit_report, Mapping) else {}
    counts = report.get("legacy_cross_source_counts")
    complete = (
        report.get("legacy_cross_source_audit_complete") is True
        and isinstance(counts, Mapping)
        and all(type(counts.get(key)) is int and counts[key] >= 0
                for key in (
                    "national_id_overlap_groups",
                    "passport_overlap_groups",
                    "repeated_legacy_passport_groups",
                ))
    )
    historical_collision = (
        not complete or any(counts[key] > 0 for key in (
            "national_id_overlap_groups",
            "passport_overlap_groups",
            "repeated_legacy_passport_groups",
        ))
    )
    report_ready = (
        complete
        and report.get("operator_review_candidate") is True
        and report.get("safe_to_execute") is False
        and report.get("production_approved") is False
        and report.get("registration_enabled") is False
    )
    return RegistrationReleaseAssessment(
        reviewable=bool(
            report_ready and not historical_collision
            and not missing_approvals and not missing_certifications
        ),
        missing_approvals=missing_approvals,
        missing_certifications=missing_certifications,
        pending_data_review=not report_ready or historical_collision,
    )
