"""Offline, pure idempotency identity for a prospective new-only loan application.

The reviewed intent is NOT a reservation: no persistence, registration, loan
creation or route. A future approved PostgreSQL reservation table must bind
(company, branch, borrower/account, employee, key, fingerprint) atomically.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import hmac
import json
import re
from uuid import UUID

from services.batlokoa_new_only_loan_handoff import NewOnlyLoanHandoffDenied


_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")


@dataclass(frozen=True, slots=True)
class NewOnlyApplicationIntent:
    company_id: UUID
    branch_id: UUID
    employee_user_id: UUID
    account_id: UUID
    product_id: UUID
    principal: Decimal
    term_count: int
    request_key: str
    request_fingerprint: str
    can_reserve: bool = False
    can_create_application: bool = False


def prepare_new_only_application_intent(
    *,
    company_id: UUID,
    branch_id: UUID,
    employee_user_id: UUID,
    account_id: UUID,
    product_id: UUID,
    principal: Decimal,
    term_count: int,
    request_key: str,
    fingerprint_secret: bytes,
) -> NewOnlyApplicationIntent:
    """Create canonical fingerprint with an HMAC secret, never a borrower ID.

    This is a proposal fingerprint, not an approval or an application ID.
    Replay verification needs a UNIQUE durable DB row and transaction locks.
    """
    if not all(
        isinstance(value, UUID) for value in (
            company_id, branch_id, employee_user_id, account_id, product_id,
        )
    ):
        raise NewOnlyLoanHandoffDenied("Trusted UUID identifiers required")
    if (
        type(principal) is not Decimal
        or not principal.is_finite()
        or principal <= 0
        or principal.as_tuple().exponent < -2
        or type(term_count) is not int
        or not 1 <= term_count <= 120
        or not isinstance(request_key, str)
        or not _KEY_PATTERN.fullmatch(request_key)
        or not isinstance(fingerprint_secret, bytes)
        or len(fingerprint_secret) < 32
    ):
        raise NewOnlyLoanHandoffDenied("Valid amount, term, key and HMAC secret required")
    canonical = json.dumps({
        "v": 1,
        "company_id": str(company_id),
        "branch_id": str(branch_id),
        "employee_user_id": str(employee_user_id),
        "account_id": str(account_id),
        "product_id": str(product_id),
        "principal": f"{principal.quantize(Decimal('0.01')):.2f}",
        "term_count": term_count,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(fingerprint_secret, canonical, hashlib.sha256).hexdigest()
    return NewOnlyApplicationIntent(
        company_id=company_id,
        branch_id=branch_id,
        employee_user_id=employee_user_id,
        account_id=account_id,
        product_id=product_id,
        principal=principal,
        term_count=term_count,
        request_key=request_key,
        request_fingerprint=digest,
    )


def check_proposed_application_replay(
    intent: NewOnlyApplicationIntent,
    *,
    stored_company_id: UUID,
    stored_request_key: str,
    stored_fingerprint: str,
    stored_status: str,
) -> str:
    """Pure decision for a row read under an eventual database row lock.

    Never returns authorization to create a loan. Replays of the same request
    cannot be treated as newly admitted work. No status automatically retries.
    """
    if (
        not isinstance(intent, NewOnlyApplicationIntent)
        or intent.can_reserve is not False
        or intent.can_create_application is not False
    ):
        raise NewOnlyLoanHandoffDenied("Unactivated application intent required")
    if (
        stored_company_id != intent.company_id
        or stored_request_key != intent.request_key
        or not isinstance(stored_fingerprint, str)
        or not hmac.compare_digest(stored_fingerprint, intent.request_fingerprint)
    ):
        raise NewOnlyLoanHandoffDenied("Idempotency key reused with different application")
    if stored_status == "completed":
        return "previously_completed_no_new_write"
    if stored_status == "reserved":
        return "already_reserved_no_new_write"
    if stored_status == "rejected":
        return "previously_rejected_no_new_write"
    raise NewOnlyLoanHandoffDenied("Unknown application reservation status")
