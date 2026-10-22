"""Legacy bank routing aligned with the existing LoanHub frontend banking policy.

These are configured *default* clearing branch codes, not a substitute for
recipient bank mandate verification. Unknown prefixes are never guessed.
"""
from __future__ import annotations

BANK_RULES = (
    ("FNB", "280061", ("6",)),
    ("STD", "060667", ("90",)),
    ("PB", "500100", ("10",)),
)


def resolve_legacy_bank(account_number: str) -> tuple[str, str] | None:
    if not account_number or not account_number.isascii() or not account_number.isdigit():
        return None
    for bank, clearing_branch, prefixes in BANK_RULES:
        if any(account_number.startswith(prefix) for prefix in prefixes):
            return bank, clearing_branch
    # Nedbank may start with any digit except prefixes reserved above.
    # Unknown longer accounts must not be silently assigned to Nedbank.
    return ("NB", "390161") if len(account_number) <= 11 else None
