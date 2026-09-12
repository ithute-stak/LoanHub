from __future__ import annotations

import re
from typing import Final


DEFAULT_BANK_BRANCH: Final[str] = "Maseru Central"

BANKING_POLICY: Final[dict[str, dict[str, object]]] = {
    "FNB": {"code": "280061", "prefixes": ("6",)},
    "PB": {"code": "500100", "prefixes": ("10",)},
    "STD": {"code": "060667", "prefixes": ("90",)},
    "NB": {"code": "390161", "prefixes": ("11", "12")},
}

BANK_NAMES: Final[tuple[str, ...]] = tuple(BANKING_POLICY)


def normalize_bank_name(value: str | None) -> str:
    name = str(value or "").strip().upper()
    if name not in BANKING_POLICY:
        raise ValueError("Bank must be one of FNB, PB, STD or NB")
    return name


def bank_code_for(bank_name: str) -> str:
    policy = BANKING_POLICY[normalize_bank_name(bank_name)]
    return str(policy["code"])


def bank_prefixes_for(bank_name: str) -> tuple[str, ...]:
    policy = BANKING_POLICY[normalize_bank_name(bank_name)]
    return tuple(str(prefix) for prefix in policy["prefixes"])


def normalize_account_number(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    cleaned = re.sub(r"[\s/-]+", "", str(value).strip())
    if not cleaned.isdigit():
        raise ValueError("Bank account number must contain digits only")
    if len(cleaned) < 4:
        raise ValueError("A valid bank account number is required")
    return cleaned


def validate_account_number_for_bank(bank_name: str, account_number: str | None) -> str | None:
    name = normalize_bank_name(bank_name)
    account = normalize_account_number(account_number)
    if account is None:
        return None

    prefixes = bank_prefixes_for(name)
    if not account.startswith(prefixes):
        if len(prefixes) == 1:
            expected = prefixes[0]
        else:
            expected = " or ".join(prefixes)
        raise ValueError(f"{name} account number must start with {expected}")
    return account


def standard_bank_fields(bank_name: str) -> tuple[str, str, str]:
    name = normalize_bank_name(bank_name)
    return name, DEFAULT_BANK_BRANCH, bank_code_for(name)
