"""Deterministic read-only fingerprint of local Principal x financial sources.

Call only after taking the tenant-scoped loan-row lock in an open PostgreSQL
transaction. This captures local state, not authoritative external reversals,
independently authenticated legacy receipts, or providers. A matching digest never enables posting.
"""
import hashlib
import json
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models.accounting import JournalEntry, JournalLine
from database.models.client_loan_company import ClientCompanyLoan
from database.models.governance_control import PaymentAdjustment
from database.models.legacy_loan_capture import LegacyLoanCapture
from database.models.origination import LoanContract
from database.models.lelefa_paygate import LelefaPayGateWebhookEvent

from database.models.cash import CashTransaction
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from database.models.treasury import TreasuryEntry


def _canonical(value):
    """Stable serialization for database identifiers, numbers, enums, times."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
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
    loans = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.id == loan_id,
    ).populate_existing().all()
    if len(loans) != 1:
        raise ValueError("Scoped financial loan not found")
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
    installments = (
        db.query(RepaymentInstallment)
        .filter(RepaymentInstallment.loan_id == loan_id)
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
    captures = db.query(LegacyLoanCapture).filter(
        LegacyLoanCapture.company_id == company_id, LegacyLoanCapture.loan_id == loan_id,
    ).all()
    contracts = db.query(LoanContract).filter(
        LoanContract.company_id == company_id, LoanContract.loan_id == loan_id,
    ).all()
    adjustments = db.query(PaymentAdjustment).join(
        PaymentTransaction, PaymentAdjustment.payment_id == PaymentTransaction.id,
    ).filter(PaymentAdjustment.company_id == company_id,
             PaymentTransaction.company_id == company_id,
             PaymentTransaction.loan_id == loan_id).all()
    events = db.query(LelefaPayGateWebhookEvent).join(
        PaymentTransaction, LelefaPayGateWebhookEvent.payment_id == PaymentTransaction.id,
    ).filter(PaymentTransaction.company_id == company_id,
             PaymentTransaction.loan_id == loan_id).all()
    payment_refs = [str(row.id) for row in payments]
    journals = db.query(JournalEntry).filter(
        JournalEntry.company_id == company_id,
        or_(
            (JournalEntry.reference_type == "treasury_entry") &
            JournalEntry.reference_id.in_([str(row.id) for row in treasury]),
            (JournalEntry.reference_type == "loan_write_off") &
            (JournalEntry.reference_id == str(loan_id)),
            (JournalEntry.reference_type == "payment_transaction") &
            JournalEntry.reference_id.in_(payment_refs),
            (JournalEntry.reference_type == "accounting_reversal") &
            JournalEntry.reference_id.in_([f"reversal:payment_transaction:{ref}" for ref in payment_refs]),
        ),
    ).all()
    lines = db.query(JournalLine).join(
        JournalEntry, JournalLine.journal_entry_id == JournalEntry.id,
    ).filter(JournalEntry.company_id == company_id,
             JournalLine.journal_entry_id.in_([row.id for row in journals])).all()
    payload = {
        "version": 4,
        "loan_state": _records(loans, (
            "id", "company_id", "branch_id", "borrower_id", "parent_loan_id",
            "principal_amount", "interest_rate", "processing_fee",
            "total_repayable", "amount_paid", "balance", "status",
            "repayment_type", "repayment_period", "installment_amount",
            "calculation_method", "calculation_breakdown",
            "disbursed_at", "first_payment_due", "maturity_date",
            "automatic_renewal_enabled", "renewal_cycle_count",
            "original_maturity_date", "last_renewed_at", "renewal_stopped_at",
            "is_top_up", "top_up_settlement_amount", "top_up_cash_amount",
            "updated_at",
        )),
        "historical_captures": _records(captures, (
            "id", "company_id", "loan_id", "status", "converted_at",
            "borrowed_amount", "total_repayable", "amount_paid", "conversion_data", "updated_at",
        )),
        "historical_contracts": _records(contracts, (
            "id", "company_id", "loan_id", "status", "contract_number",
            "contract_hash", "terms_snapshot", "updated_at",
        )),
        "adjustments": _records(adjustments, (
            "id", "company_id", "payment_id", "approval_request_id", "adjustment_type",
            "amount", "currency", "status", "requested_by_user_id", "approved_by_user_id",
            "approved_at", "completed_at", "provider_reference", "updated_at",
        )),
        "gateway_events": _records(events, (
            "id", "event_id", "event_type", "payment_id", "payload_hash", "payload",
            "processing_status", "processing_error", "processed_at",
        )),
        "journals": _records(journals, (
            "id", "company_id", "branch_id", "scope_key", "reference_type", "reference_id",
            "status", "total_debit", "total_credit", "posted_at", "voided_at", "updated_at",
        )),
        "journal_lines": _records(lines, (
            "id", "journal_entry_id", "account_id", "debit", "credit", "updated_at",
        )),
        "company_id": str(company_id), "loan_id": str(loan_id),
        "payments": _records(payments, (
            "id", "company_id", "loan_id", "amount", "currency",
            "status", "direction", "purpose", "payment_method",
            "provider", "provider_reference", "proof_reference",
            "completed_at", "verified_at", "verified_by_user_id", "provider_payload",
            "provider_operation", "configuration_scope", "idempotency_key",
            "borrower_id", "company_borrower_account_id", "updated_at",
        )),
        "cash": _records(cash, (
            "id", "payment_id", "direction", "tendered_amount",
            "applied_amount", "change_amount", "forward_amount",
            "updated_at",
        )),
        "installments": _records(installments, (
            "id", "loan_id", "renewal_cycle_id", "superseded_by_cycle_id",
            "is_superseded", "superseded_at", "installment_number",
            "due_date", "principal_due", "interest_due", "fee_due",
            "total_due", "paid_amount", "status", "paid_at",
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
