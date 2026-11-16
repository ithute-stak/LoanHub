"""Fail-closed single-use Wacom execution challenge gate.

This validates persisted ceremony linkage and chronology only. Workstation-key
possession is NOT physical STU-540 attestation. Never use this module to mark
a loan signed or to authorize a legal execution transaction by itself.
"""
from datetime import datetime, timedelta, timezone
import hmac

MAX_AGE = timedelta(minutes=2)


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _same_hash(left, right):
    return (isinstance(left, str) and isinstance(right, str)
            and len(left) == len(right) == 64
            and all(c in "0123456789abcdef" for c in left + right)
            and hmac.compare_digest(left, right))


def challenge_execution_blockers(*, challenge, intent, authorization, receipt,
                                 candidate_sha256, now=None):
    """Pure denial checks; an empty list never authorizes legal execution."""
    now = _utc(now or datetime.now(timezone.utc))
    if now is None:
        return ["invalid_challenge_clock"]
    if any(x is None for x in (challenge, intent, authorization, receipt)):
        return ["missing_execution_challenge"]
    issues = []
    if (challenge.company_id != intent.company_id
            or challenge.borrower_id != intent.borrower_id
            or challenge.contract_id != intent.contract_id
            or challenge.intent_id != intent.id
            or challenge.authorization_id != authorization.id
            or challenge.receipt_id != receipt.id
            or challenge.workstation_id != intent.workstation_id
            or receipt.contract_id != intent.contract_id
            or receipt.authorization_id != authorization.id):
        issues.append("challenge_reference_mismatch")
    if (not _same_hash(challenge.candidate_sha256, candidate_sha256)
            or not _same_hash(challenge.candidate_sha256, receipt.executed_pdf_sha256)
            or not _same_hash(challenge.field_binding_sha256,
                              authorization.field_binding_sha256)
            or not _same_hash(challenge.challenge_sha256,
                              challenge.challenge_sha256)):
        issues.append("challenge_document_binding_mismatch")
    requested, expires = _utc(challenge.requested_at), _utc(challenge.expires_at)
    if (challenge.status != "verified" or challenge.verified_at is None
            or challenge.consumed_at is not None):
        issues.append("challenge_not_single_use_ready")
    if (requested is None or expires is None
            or not requested <= now < expires
            or expires - requested > MAX_AGE):
        issues.append("challenge_expired_or_invalid")
    verified = _utc(challenge.verified_at)
    if verified is None or requested is None or not requested <= verified <= now:
        issues.append("challenge_verification_time_invalid")
    # These are recorded preconditions, not assertions of physical pen proof.
    workstation = _utc(challenge.workstation_proof_at)
    borrower = _utc(challenge.borrower_affirmed_at)
    if (workstation is None or borrower is None or requested is None
            or not requested <= workstation <= now
            or not requested <= borrower <= now
            or challenge.workstation_proof_by is None
            or challenge.borrower_affirmed_user_id is None
            or not _same_hash(challenge.workstation_proof_sha256,
                              challenge.workstation_proof_sha256)
            or not _same_hash(challenge.borrower_affirmation_sha256,
                              challenge.borrower_affirmation_sha256)):
        issues.append("challenge_evidence_incomplete")
    return issues
