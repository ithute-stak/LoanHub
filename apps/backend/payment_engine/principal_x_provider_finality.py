"""Provider-finality evidence contract for Principal x payment posting.

No external provider call is made here. The trusted payment adapter must
verify a provider-signed response or independently fetched final settlement
record and bind it to the exact loan, tenant, amount, currency and reference.
Never treat a callback payload or client-supplied flag as proof of settlement.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from payment_engine.principal_x_collection_ceiling import money


@dataclass(frozen=True)
class ProviderFinalityEvidence:
    company_id: UUID
    loan_id: UUID
    provider: str
    provider_reference: str
    verification_reference: str
    idempotency_key: str
    amount: Decimal
    currency: str
    final_status: str
    verified_at: datetime
    independently_verified: bool


def require_provider_finality(
    *, evidence: ProviderFinalityEvidence, company_id: UUID, loan_id: UUID,
    expected_amount: Decimal, expected_provider_reference: str,
    expected_idempotency_key: str,
) -> ProviderFinalityEvidence:
    """Validate trusted adapter output; does not authenticate the provider.

    Only the server-side provider adapter may construct evidence after a
    successful verification call. A user request must never supply it.
    """
    if evidence.company_id != company_id or evidence.loan_id != loan_id:
        raise ValueError("Provider evidence loan/company mismatch")
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified UUIDs required")
    if not evidence.independently_verified or evidence.final_status != "succeeded":
        raise ValueError("Independently verified final settlement required")
    if not isinstance(evidence.provider, str) or not evidence.provider.strip():
        raise ValueError("Provider identity required")
    if not isinstance(evidence.verification_reference, str) or not evidence.verification_reference.strip():
        raise ValueError("Verification reference required")
    if not expected_provider_reference or evidence.provider_reference != expected_provider_reference:
        raise ValueError("Provider reference mismatch")
    if not expected_idempotency_key or evidence.idempotency_key != expected_idempotency_key:
        raise ValueError("Idempotency key mismatch")
    if evidence.currency != "LSL":
        raise ValueError("Currency mismatch")
    if money(evidence.amount) <= 0 or money(evidence.amount) != money(expected_amount):
        raise ValueError("Provider-confirmed amount mismatch")
    stamp = evidence.verified_at
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("Timezone-aware verification timestamp required")
    if stamp.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError("Verification timestamp cannot be in the future")
    return evidence
