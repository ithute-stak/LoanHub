"""Pure immutable double-entry journal proposal. Never posts to a ledger."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from financial_allocation import Allocation, cents

class JournalError(ValueError):
    pass

@dataclass(frozen=True)
class Line:
    account: str
    debit: Decimal
    credit: Decimal

@dataclass(frozen=True)
class Journal:
    reference: str
    currency: str
    lines: tuple[Line, ...]

def validate_journal(journal: Journal) -> None:
    if not journal.reference or journal.currency != "LSL" or len(journal.lines) < 2:
        raise JournalError("Missing journal metadata")
    debits, credits = Decimal("0.00"), Decimal("0.00")
    for line in journal.lines:
        if not isinstance(line.account, str) or not line.account.strip():
            raise JournalError("Invalid account")
        try:
            cents(line.debit)
            cents(line.credit)
        except ValueError as exc:
            raise JournalError("Invalid monetary line") from exc
        if (line.debit > 0) == (line.credit > 0):
            raise JournalError("Each line must be debit XOR credit")
        debits += line.debit
        credits += line.credit
    if debits <= 0 or debits != credits:
        raise JournalError("Journal is not balanced")

def propose_received_collection_journal(*, allocation: Allocation, reference: str,
                                        clearing_account: str,
                                        receivable_accounts: dict[str, str]) -> Journal:
    if not reference or not clearing_account or not isinstance(receivable_accounts, dict):
        raise JournalError("Missing authoritative accounting mapping")
    if set(receivable_accounts) != set(allocation.allocated):
        raise JournalError("Incomplete receivable account map")
    if not all(isinstance(a, str) and a.strip() for a in receivable_accounts.values()):
        raise JournalError("Invalid accounting mapping")
    accounts = [clearing_account, *receivable_accounts.values()]
    if len(set(accounts)) != len(accounts):
        raise JournalError("Debit and credit accounts must differ")
    if allocation.unapplied != Decimal("0.00") or allocation.allocated_total != allocation.requested:
        raise JournalError("Unbalanced allocation")
    lines = [Line(clearing_account, allocation.requested, Decimal("0.00"))]
    for component, value in allocation.allocated.items():
        if value:
            lines.append(Line(receivable_accounts[component], Decimal("0.00"), value))
    proposed = Journal(reference, "LSL", tuple(lines))
    validate_journal(proposed)
    return proposed
