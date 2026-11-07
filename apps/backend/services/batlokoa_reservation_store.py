"""Phase 36: isolated, non-routed PostgreSQL reservation building block.

No production table is created here and this module is not imported by any
API router. The caller must supply a certified transaction-scoped tenant
context, approved loan/borrower authorization, and a deliberately installed
schema. This is NOT a payment or an authority to debit funds.

Transactions are owned by the caller: this function never commits, rolls back,
contacts a provider, or modifies LoanHub payment and loan balance tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint, Column, ForeignKey, MetaData, Numeric, String, Table,
    UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session

# Deliberately not bound to LoanHub Base.metadata or imported into models/__init__.
# A separate reviewed migration is required before this table can exist.
reservation_metadata = MetaData()
reservation_table = Table(
    "batlokoa_collection_intent_reservations",
    reservation_metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("company_id", PG_UUID(as_uuid=True), nullable=False),
    Column("loan_id", PG_UUID(as_uuid=True), nullable=False),
    Column("borrower_id", PG_UUID(as_uuid=True), nullable=False),
    Column("idempotency_key", String(128), nullable=False),
    Column("request_fingerprint", String(64), nullable=False),
    Column("amount", Numeric(18, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("state", String(24), nullable=False),
    UniqueConstraint("company_id", "idempotency_key", name="uq_batlokoa_reservation_tenant_key"),
    CheckConstraint("amount > 0", name="ck_batlokoa_reservation_positive_amount"),
    CheckConstraint("currency = 'LSL'", name="ck_batlokoa_reservation_lsl"),
    CheckConstraint("state IN ('reserved', 'previewed', 'rejected', 'expired')",
                    name="ck_batlokoa_reservation_state"),
    CheckConstraint("request_fingerprint ~ '^[0-9a-f]{64}$'",
                    name="ck_batlokoa_reservation_fingerprint"),
)

class ReservationError(ValueError):
    pass

class ReservationDecision(str, Enum):
    CREATED = "created"
    REPLAY = "same_request"
    CONFLICT = "conflict"

@dataclass(frozen=True, slots=True)
class ReservationRequest:
    company_id: UUID
    loan_id: UUID
    borrower_id: UUID
    idempotency_key: str
    request_fingerprint: str
    amount: Decimal
    currency: str = "LSL"

@dataclass(frozen=True, slots=True)
class ReservationOutcome:
    decision: ReservationDecision
    reservation_id: UUID

def validate_request(request: ReservationRequest) -> None:
    if not isinstance(request, ReservationRequest):
        raise ReservationError("Validated reservation request required")
    if not all(isinstance(v, UUID) for v in
               (request.company_id, request.loan_id, request.borrower_id)):
        raise ReservationError("Verified UUID identifiers required")
    if not isinstance(request.idempotency_key, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{16,128}", request.idempotency_key
    ):
        raise ReservationError("Invalid request key")
    if not isinstance(request.request_fingerprint, str) or not re.fullmatch(
        r"[0-9a-f]{64}", request.request_fingerprint
    ):
        raise ReservationError("Invalid fingerprint")
    if request.currency != "LSL":
        raise ReservationError("Unsupported currency")
    if not isinstance(request.amount, Decimal) or not request.amount.is_finite():
        raise ReservationError("Finite Decimal required")
    if (request.amount <= 0 or request.amount > Decimal("9999999999999999.99")
            or request.amount != request.amount.quantize(Decimal("0.01"))):
        raise ReservationError("Positive exact LSL cents required")

def reserve_in_existing_transaction(
    db: Session,
    *,
    request: ReservationRequest,
    verified_company_id: UUID,
    enabled: bool = False,
) -> ReservationOutcome:
    """Atomic PostgreSQL insert-or-classify inside an EXISTING transaction.

    Caller must provide a trusted company ID from authenticated tenant
    resolution (not a request field). A unique(company_id,key) constraint
    serializes concurrent conflicting requests. No commit occurs here.

    Important: a reservation merely deduplicates a proposed operation.
    It does not lock a loan balance, approve a mandate, or authorize a debit.
    """
    if not enabled:
        raise ReservationError("Phase 36 reservation write path is disabled")
    validate_request(request)
    if not isinstance(verified_company_id, UUID) or request.company_id != verified_company_id:
        raise ReservationError("Unverified company boundary")
    if not db.in_transaction():
        raise ReservationError("Caller must own an active transaction")
    new_id = uuid4()
    created = db.execute(text("""
        INSERT INTO batlokoa_collection_intent_reservations (
            id, company_id, loan_id, borrower_id, idempotency_key,
            request_fingerprint, amount, currency, state
        ) VALUES (
            :id, :company_id, :loan_id, :borrower_id, :idempotency_key,
            :request_fingerprint, :amount, 'LSL', 'reserved'
        )
        ON CONFLICT (company_id, idempotency_key) DO NOTHING
        RETURNING id
    """), {
        "id": new_id,
        "company_id": request.company_id,
        "loan_id": request.loan_id,
        "borrower_id": request.borrower_id,
        "idempotency_key": request.idempotency_key,
        "request_fingerprint": request.request_fingerprint,
        "amount": request.amount,
    }).scalar_one_or_none()
    if created is not None:
        return ReservationOutcome(ReservationDecision.CREATED, created)
    existing = db.execute(text("""
        SELECT id, loan_id, borrower_id, request_fingerprint, amount, currency
        FROM batlokoa_collection_intent_reservations
        WHERE company_id = :company_id AND idempotency_key = :idempotency_key
        FOR UPDATE
    """), {"company_id": request.company_id,
           "idempotency_key": request.idempotency_key}).mappings().one_or_none()
    if existing is None:
        # E.g. a concurrent deletion; do not infer a safe new request.
        raise ReservationError("Reservation was not found following unique conflict")
    matches = (
        existing["loan_id"] == request.loan_id
        and existing["borrower_id"] == request.borrower_id
        and existing["request_fingerprint"] == request.request_fingerprint
        and existing["amount"] == request.amount
        and existing["currency"] == request.currency
    )
    return ReservationOutcome(
        ReservationDecision.REPLAY if matches else ReservationDecision.CONFLICT,
        existing["id"],
    )
