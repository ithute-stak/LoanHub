"""FUTURE ONLY: uninstalled transactional PostgreSQL intent reservation sketch.

Not imported by API, not an approved migration or payment reservation.
Caller must ensure tenant RLS, authorization and transaction boundaries.
"""
from __future__ import annotations
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session

FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
KEY = re.compile(r"^[A-Za-z0-9_-]{16,128}$")

class ReservationStatus(str, Enum):
    CREATED = "created"
    SAME_REQUEST = "same_request"
    CONFLICT = "conflict"

@dataclass(frozen=True)
class ReservationResult:
    status: ReservationStatus
    reservation_id: UUID

def reserve_collection_intent(
    db: Session, *, company_id: UUID, loan_id: UUID, borrower_id: UUID,
    idempotency_key: str, request_fingerprint: str, amount: Decimal,
) -> ReservationResult:
    if not all(isinstance(v, UUID) for v in (company_id, loan_id, borrower_id)):
        raise ValueError("Trusted identifiers must be UUIDs")
    if not isinstance(idempotency_key, str) or not KEY.fullmatch(idempotency_key):
        raise ValueError("Invalid idempotency key")
    if not isinstance(request_fingerprint, str) or not FINGERPRINT.fullmatch(request_fingerprint):
        raise ValueError("Invalid request fingerprint")
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        raise ValueError("Invalid amount")
    if amount > Decimal("9999999999999999.99") or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Invalid amount precision")
    new_id = uuid.uuid4()
    inserted = db.execute(text("""
        INSERT INTO batlokoa_collection_intent_reservations
          (id, company_id, loan_id, borrower_id, idempotency_key,
           request_fingerprint, amount, currency, state)
        VALUES (:id, :company_id, :loan_id, :borrower_id, :key,
                :fingerprint, :amount, 'LSL', 'reserved')
        ON CONFLICT (company_id, idempotency_key) DO NOTHING RETURNING id
    """), {
        "id": new_id, "company_id": company_id, "loan_id": loan_id,
        "borrower_id": borrower_id, "key": idempotency_key,
        "fingerprint": request_fingerprint, "amount": amount,
    }).scalar_one_or_none()
    if inserted is not None:
        return ReservationResult(ReservationStatus.CREATED, inserted)
    row = db.execute(text("""
        SELECT id, loan_id, borrower_id, request_fingerprint, amount, currency
          FROM batlokoa_collection_intent_reservations
         WHERE company_id = :company_id AND idempotency_key = :key
         FOR UPDATE
    """), {"company_id": company_id, "key": idempotency_key}).mappings().one_or_none()
    if row is None:
        raise RuntimeError("Reservation disappeared during transaction")
    if (row["loan_id"] != loan_id or row["borrower_id"] != borrower_id or
        row["request_fingerprint"] != request_fingerprint or
        row["amount"] != amount or row["currency"] != "LSL"):
        return ReservationResult(ReservationStatus.CONFLICT, row["id"])
    return ReservationResult(ReservationStatus.SAME_REQUEST, row["id"])
