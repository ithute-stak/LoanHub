"""Tenant-scoped, read-only trial-balance parity diagnostic.

Uses compact local numeric IDs because LoanHub's real account IDs are UUIDs.
Never writes, commits, changes report totals, or grants posting authority.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from database.models.accounting import JournalEntry, JournalLine
from services.accounting_native_runtime import advisory_trial_balance


def scoped_trial_balance_parity(db, *, scope_key: str, from_date: date, to_date: date, branch_id=None) -> dict:
    if not scope_key or from_date > to_date:
        raise ValueError("valid scope and date range required")
    query = db.query(JournalLine.account_id, JournalLine.debit, JournalLine.credit).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        JournalEntry.scope_key == scope_key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date.between(from_date, to_date),
    )
    if branch_id is not None:
        query = query.filter(JournalEntry.branch_id == branch_id)
    source = query.all()
    # Assign ephemeral numeric IDs deterministically. No persistent mapping or
    # cross-tenant account identifier is disclosed to the native library.
    keys = sorted({str(item[0]) for item in source})
    mapping = {key: idx + 1 for idx, key in enumerate(keys)}
    rows = [
        (mapping[str(account_id)], Decimal(debit), Decimal(credit))
        for account_id, debit, credit in source
    ]
    parity = advisory_trial_balance(rows)
    return {
        "scope_key": scope_key,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id is not None else None,
        "journal_line_count": len(rows),
        "account_count": len(keys),
        "native_cpp_matched": parity["native_cpp_matched"],
        "authoritative": False,
        "python_trial_balance": parity["python_trial_balance"],
    }
