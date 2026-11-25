"""Deterministic read-only fingerprint of local Principal x financial sources.

Call only after taking the tenant-scoped loan-row lock in an open PostgreSQL
transaction. This captures local state, not authoritative external reversals,
legacy imports, or providers. A matching digest never enables posting.
"""
import hashlib
import json
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cash import CashTransaction
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from database.models.treasury import TreasuryEntry


def _canonical(value):
    """Stable serialization for database identifiers, numbers, enums, times."""
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _records(rows, fields):
    result = []
    for row in rows:
        result.append([_canonical(getattr(row, field, None)) for field in fields])
    # Sorting serialized full rows ensures order independence and still keeps
    # duplicate rows visible in the snapshot.
    return sorted(result, key=lambda item: json.dumps(item, separators=(",", ":")))


def local_principal_x_source_revision(
    db: Session, *, company_id: UUID, loan_id: UUID,
) -> str:
    """Hash all selected local records for one tenant-scoped loan.

    Not safe as an independent payment/ledger certification. The caller must
    hold the loan lock; independent writers may not honor that lock.
    """
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified company and loan UUIDs required")
    payments = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.company_id == company_id,
                PaymentTransaction.loan_id == loan_id)
        .all()
    )
    cash = (
        db.query(CashTransaction)
        .join(PaymentTransaction, CashTransaction.payment_id == PaymentTransaction.id)
        .filter(PaymentTransaction.company_id == company_id,
                PaymentTransaction.loan_id == loan_id)
        .all()
    )
    allocations = (
        db.query(PaymentAllocation)
        .join(RepaymentInstallment,
              PaymentAllocation.installment_id == RepaymentInstallment.id)
        .filter(RepaymentInstallment.loan_id == loan_id)
        .all()
    )
    treasury = (
        db.query(TreasuryEntry)
        .filter(TreasuryEntry.company_id == company_id,
                TreasuryEntry.loan_id == loan_id)
        .all()
    )
    payload = {
        "version": 1,
        "company_id": str(company_id), "loan_id": str(loan_id),
        "payments": _records(payments, (
            "id", "company_id", "loan_id", "amount", "currency",
            "status", "direction", "purpose", "payment_method",
            "provider", "provider_reference", "proof_reference",
            "completed_at", "verified_at", "updated_at",
        )),
        "cash": _records(cash, (
            "id", "payment_id", "direction", "tendered_amount",
            "applied_amount", "change_amount", "forward_amount",
            "updated_at",
        )),
        "allocations": _records(allocations, (
            "id", "payment_id", "installment_id", "amount", "updated_at",
        )),
        "treasury": _records(treasury, (
            "id", "company_id", "loan_id", "payment_transaction_id",
            "amount", "currency", "direction", "entry_type",
            "approval_status", "is_voided", "updated_at",
        )),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
