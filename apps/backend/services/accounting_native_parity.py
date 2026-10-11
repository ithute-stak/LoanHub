"""Advisory Python/C++ trial balance parity; never posts to the ledger.

Account identifiers here are numeric surrogate IDs accepted by the native ABI.
Callers must obtain posted journal lines from their already scoped queries.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Callable, Iterable

MAX_CENTS = 2**63 - 1
MIN_CENTS = -(2**63)


def _cents(value: Decimal) -> int:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("amount must be finite Decimal")
    scaled = value * 100
    if scaled != scaled.to_integral_value():
        raise ValueError("amount must have at most two decimal places")
    cents = int(scaled)
    if not MIN_CENTS <= cents <= MAX_CENTS:
        raise OverflowError("amount exceeds signed 64-bit cents")
    return cents


def reference_trial_balance(rows: Iterable[tuple[int, Decimal, Decimal]]) -> str:
    """Deterministic read-only trial balance in native wire format."""
    totals: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    debits = credits = 0
    for account_id, debit, credit in rows:
        if not isinstance(account_id, int) or isinstance(account_id, bool) or account_id <= 0:
            raise ValueError("numeric account ID required")
        d, c = _cents(debit), _cents(credit)
        if d < 0 or c < 0 or (d == 0) == (c == 0):
            raise ValueError("journal line must have one positive side")
        totals[account_id][0] += d
        totals[account_id][1] += c
        debits += d
        credits += c
    if any(abs(v) > MAX_CENTS for values in totals.values() for v in values):
        raise OverflowError("account total exceeds signed 64-bit cents")
    if any(abs(v) > MAX_CENTS for v in (debits, credits)):
        raise OverflowError("trial total exceeds signed 64-bit cents")
    output = [f"{debits}|{credits}"]
    for account_id, (d, c) in sorted(totals.items()):
        net = d - c
        if not MIN_CENTS <= net <= MAX_CENTS:
            raise OverflowError("account net exceeds signed 64-bit cents")
        output.append(f"{account_id}|{d}|{c}|{net}")
    return "\n".join(output) + "\n"


def compare_trial_balance(
    rows: Iterable[tuple[int, Decimal, Decimal]],
    native_execute: Callable[[str, str], str | None],
) -> dict:
    """Fail closed to Python on native error, absence, or mismatch.

    The result is diagnostic only. The returned parity flag must not change
    accounting posting, approval, reconciliation, or authoritative reports.
    """
    entries = list(rows)
    expected = reference_trial_balance(entries)
    payload = "".join(
        f"{account_id}|{_cents(debit)}|{_cents(credit)}\n"
        for account_id, debit, credit in entries
    )
    try:
        actual = native_execute("accounting-trial-balance", payload)
    except Exception:
        actual = None
    return {
        "python_trial_balance": expected,
        "native_cpp_matched": actual == expected,
        "authoritative": False,
    }
