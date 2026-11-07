"""Phase 37: dormant tenant-security and immutable evidence contract.

Pure functions only. Not wired to payment APIs, provider callbacks or live
PostgreSQL migrations. Does NOT authorize financial execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import hmac
import json
import re
from uuid import UUID


class EvidenceIntegrityError(ValueError):
    pass


def _uuid(value: UUID) -> str:
    if not isinstance(value, UUID):
        raise EvidenceIntegrityError("Trusted UUID required")
    return str(value)


def _money(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise EvidenceIntegrityError("Finite decimal required")
    if value <= 0 or value > Decimal("9999999999999999.99"):
        raise EvidenceIntegrityError("Amount out of range")
    if value != value.quantize(Decimal("0.01")):
        raise EvidenceIntegrityError("Exact currency precision required")
    return format(value, ".2f")


@dataclass(frozen=True, slots=True)
class ReservationEvidence:
    company_id: UUID
    reservation_id: UUID
    loan_id: UUID
    borrower_id: UUID
    amount: Decimal
    request_fingerprint: str
    event_type: str
    event_sequence: int
    previous_digest: str | None


_ALLOWED = frozenset({"reserved", "previewed", "rejected", "expired"})


def hash_reservation_evidence(value: ReservationEvidence) -> str:
    """Canonical hash-chain step; integrity evidence, NOT a digital signature.

    A privileged database attacker able to rewrite both evidence and digest
    can recompute a whole chain. Production-grade immutability requires
    restricted roles, controlled writes, external anchoring and audit review.
    """
    if not isinstance(value, ReservationEvidence):
        raise EvidenceIntegrityError("Structured event required")
    if value.event_type not in _ALLOWED:
        raise EvidenceIntegrityError("Unsupported transition evidence")
    if type(value.event_sequence) is not int or value.event_sequence < 1:
        raise EvidenceIntegrityError("Positive event sequence required")
    if not isinstance(value.request_fingerprint, str) or not re.fullmatch(
        r"[0-9a-f]{64}", value.request_fingerprint
    ):
        raise EvidenceIntegrityError("Invalid request fingerprint")
    if value.previous_digest is None:
        if value.event_sequence != 1:
            raise EvidenceIntegrityError("Genesis event must have sequence 1")
    elif (not isinstance(value.previous_digest, str)
          or not re.fullmatch(r"[0-9a-f]{64}", value.previous_digest)
          or value.event_sequence == 1):
        raise EvidenceIntegrityError("Invalid chain link")
    payload = {
        "v": 1,
        "company_id": _uuid(value.company_id),
        "reservation_id": _uuid(value.reservation_id),
        "loan_id": _uuid(value.loan_id),
        "borrower_id": _uuid(value.borrower_id),
        "amount": _money(value.amount),
        "currency": "LSL",
        "request_fingerprint": value.request_fingerprint,
        "event_type": value.event_type,
        "event_sequence": value.event_sequence,
        "previous_digest": value.previous_digest,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def verify_evidence_chain(
    events: tuple[ReservationEvidence, ...], expected_tip: str
) -> bool:
    """Validate exact ordering, tenant continuity and previous digests."""
    if not isinstance(events, tuple) or not events:
        raise EvidenceIntegrityError("Nonempty ordered evidence required")
    first = events[0]
    anchor = (first.company_id, first.reservation_id, first.loan_id, first.borrower_id)
    digest = None
    for index, item in enumerate(events, 1):
        if item.event_sequence != index:
            raise EvidenceIntegrityError("Missing or duplicated evidence sequence")
        if (item.company_id, item.reservation_id, item.loan_id, item.borrower_id) != anchor:
            raise EvidenceIntegrityError("Cross-reservation evidence link")
        if item.previous_digest != digest:
            raise EvidenceIntegrityError("Broken evidence chain")
        digest = hash_reservation_evidence(item)
    if not isinstance(expected_tip, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_tip):
        raise EvidenceIntegrityError("Invalid expected digest")
    return hmac.compare_digest(digest, expected_tip)
