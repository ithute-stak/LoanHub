"""Pure creation gate for a future single-use Wacom execution ceremony.

No endpoint issues a challenge. No uploaded evidence can self-attest hardware
verification. This gate only checks whether a database record MAY be requested
after independent archive and tenant-scoped contract verification.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from services.wacom_execution_preflight import _utc, _hash_equal


def ceremony_challenge_blockers(
    *, intent, authorization, receipt, contract, candidate_file,
    requesting_user_id, existing_challenge=None, now=None,
):
    now = _utc(now or datetime.now(timezone.utc))
    if now is None:
        return ["invalid_clock"]
    if any(row is None for row in (intent, authorization, receipt, contract, candidate_file)):
        return ["missing_ceremony_context"]
    denial = []
    if existing_challenge is not None:
        denial.append("ceremony_already_created")
    if any(row.company_id != intent.company_id for row in (
        authorization, receipt, contract, candidate_file,
    )):
        denial.append("tenant_mismatch")
    if (
        authorization.intent_id != intent.id
        or authorization.contract_id != intent.contract_id
        or receipt.intent_id != intent.id
        or receipt.contract_id != intent.contract_id
        or receipt.authorization_id != authorization.id
        or receipt.executed_file_id != candidate_file.id
        or contract.id != intent.contract_id
        or contract.borrower_id != intent.borrower_id
        or contract.pdf_file_id != intent.source_file_id
        or str(contract.version) != intent.document_version
    ):
        denial.append("ceremony_reference_mismatch")
    if (
        receipt.status != "reserved"
        or receipt.executed_at is not None
        or authorization.status != "approved"
        or authorization.consumed_at is not None
        or not authorization.authorized_by
        or _utc(getattr(authorization, "expires_at", None)) is None
        or _utc(authorization.expires_at) <= now
    ):
        denial.append("ceremony_not_eligible")
    if (
        contract.status == "signed"
        or contract.borrower_signed_at is not None
        or contract.locked_at is not None
    ):
        denial.append("contract_already_executed")
    if not (
        _hash_equal(receipt.executed_pdf_sha256, candidate_file.checksum_sha256)
        and _hash_equal(receipt.field_binding_sha256, authorization.field_binding_sha256)
        and _hash_equal(intent.document_sha256, receipt.document_sha256)
    ):
        denial.append("ceremony_hash_mismatch")
    if (
        candidate_file.is_deleted or not candidate_file.is_encrypted
        or not candidate_file.is_confidential
        or candidate_file.scan_status != "clean"
        or candidate_file.mime_type != "application/pdf"
        or candidate_file.category != "wacom_execution_candidate"
    ):
        denial.append("ceremony_candidate_untrusted")
    if (
        requesting_user_id is None
        or requesting_user_id in {
            intent.operator_user_id, intent.review_by, authorization.requested_by,
            authorization.authorized_by, receipt.reserved_by,
        }
    ):
        denial.append("ceremony_requester_not_independent")
    return denial


def challenge_lifetime_blockers(*, requested_at, expires_at, now=None):
    now = _utc(now or datetime.now(timezone.utc))
    requested, expires = _utc(requested_at), _utc(expires_at)
    if now is None or requested is None or expires is None:
        return ["challenge_clock_invalid"]
    if requested > now or expires <= now or expires - requested > timedelta(minutes=2):
        return ["challenge_not_fresh"]
    return []
