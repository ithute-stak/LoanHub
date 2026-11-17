"""Conservative review policy for employee-assisted client registration.

Review is deliberately advisory and read-only. A clear result never authorizes
a write, because an identity can be registered concurrently or matched through
historical, corrupted or incomplete records.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationReviewDecision:
    decision: str
    can_commit: bool
    requires_human_review: bool
    identity_match_found: bool
    legacy_capture_found: bool


def decide_registration_review(
    *,
    identity_match_found: bool,
    legacy_capture_count: int,
    already_company_client: bool,
    has_existing_loans: bool,
) -> RegistrationReviewDecision:
    if any(type(v) is not bool for v in (
        identity_match_found, already_company_client, has_existing_loans
    )):
        raise ValueError("Review flags must be verified booleans")
    if type(legacy_capture_count) is not int or not 0 <= legacy_capture_count <= 1000000:
        raise ValueError("Invalid legacy count")
    conflict = (
        identity_match_found or legacy_capture_count > 0
        or already_company_client or has_existing_loans
    )
    return RegistrationReviewDecision(
        decision=("manual_review_required" if conflict else
                  "new_identity_candidate"),
        can_commit=False,
        requires_human_review=True,
        identity_match_found=identity_match_found,
        legacy_capture_found=legacy_capture_count > 0,
    )
