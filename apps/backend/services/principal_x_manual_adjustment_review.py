"""Read-only reconciliation of loan-linked manual Treasury entries and journals."""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_

from database.models.accounting import JournalEntry
from database.models.enums import TreasuryEntryType
from database.models.treasury import TreasuryEntry


@dataclass(frozen=True)
class ManualAdjustmentReview:
    treasury_count: int
    missing_journal_count: int
    inconsistent_journal_count: int
    write_off_journal_count: int
    complete: bool = False


def _money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Invalid accounting amount")
    return amount


def review_manual_adjustments(*, company_id, loan_id, treasury, journals):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    indexed = {}
    write_offs = 0
    for journal in journals:
        if journal.company_id != company_id:
            raise ValueError("Journal scope mismatch")
        key = (journal.reference_type, journal.reference_id)
        indexed.setdefault(key, []).append(journal)
        if key == ("loan_write_off", str(loan_id)) and journal.status == "posted":
            write_offs += 1
    missing = inconsistent = reviewed = 0
    for entry in treasury:
        if entry.company_id != company_id or entry.loan_id != loan_id:
            raise ValueError("Treasury scope mismatch")
        if entry.payment_transaction_id is not None:
            continue
        status = getattr(entry.approval_status, "value", entry.approval_status)
        if entry.is_voided or status not in {"posted", "approved"}:
            continue
        if entry.entry_type not in {TreasuryEntryType.ADJUSTMENT, TreasuryEntryType.MANUAL_INCOME,
                                    TreasuryEntryType.REFUND, TreasuryEntryType.LOAN_COLLECTION,
                                    TreasuryEntryType.OTHER}:
            continue
        reviewed += 1
        matches = indexed.get(("treasury_entry", str(entry.id)), [])
        if not matches:
            missing += 1
            continue
        if len(matches) != 1:
            inconsistent += 1
            continue
        journal = matches[0]
        try:
            amount = _money(entry.amount)
            debit = credit = Decimal("0")
            for line in journal.lines:
                d, c = _money(line.debit), _money(line.credit)
                if bool(d) == bool(c):
                    raise ValueError("Invalid journal line")
                debit += d
                credit += c
            if (amount <= 0 or entry.currency != "LSL" or journal.status != "posted"
                or journal.voided_at is not None or journal.branch_id != entry.branch_id
                or debit != amount or credit != amount
                or _money(journal.total_debit) != debit or _money(journal.total_credit) != credit):
                raise ValueError("Journal does not corroborate Treasury amount")
        except (ValueError, TypeError, ArithmeticError):
            inconsistent += 1
    return ManualAdjustmentReview(reviewed, missing, inconsistent, write_offs)


def inspect_manual_adjustments(db, *, company_id: UUID, loan_id: UUID):
    if not isinstance(company_id, UUID) or not isinstance(loan_id, UUID):
        raise ValueError("Verified scope required")
    treasury = db.query(TreasuryEntry).filter(
        TreasuryEntry.company_id == company_id, TreasuryEntry.loan_id == loan_id,
        TreasuryEntry.payment_transaction_id.is_(None),
    ).all()
    journals = db.query(JournalEntry).filter(
        JournalEntry.company_id == company_id,
        or_(
            (JournalEntry.reference_type == "treasury_entry") &
            JournalEntry.reference_id.in_([str(row.id) for row in treasury]),
            (JournalEntry.reference_type == "loan_write_off") &
            (JournalEntry.reference_id == str(loan_id)),
        ),
    ).all()
    return review_manual_adjustments(company_id=company_id, loan_id=loan_id,
                                     treasury=treasury, journals=journals)
