from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text


_COMPANY_SPECIAL_CASES = {
    "batlokoa financial service": "BFS",
    "batlokoa financial services": "BFS",
}
_GROUP_SPECIAL_CASES = {
    "lesotho defence force": "LDF",
    "lesotho defense force": "LDF",
}
_STOP_WORDS = {
    "pty",
    "ltd",
    "limited",
    "inc",
    "incorporated",
    "company",
    "co",
    "the",
}


def _normalized_words(value: str | None) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", str(value or "").lower())


def _safe_code(value: str | None, *, fallback: str = "GEN", max_length: int = 8) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()
    return (cleaned[:max_length] or fallback).upper()


def company_folio_code(name: str | None) -> str:
    """Return a stable, human-readable company code for folio presentation."""
    normalized = " ".join(_normalized_words(name))
    if normalized in _COMPANY_SPECIAL_CASES:
        return _COMPANY_SPECIAL_CASES[normalized]

    words = [word for word in _normalized_words(name) if word not in _STOP_WORDS]
    if not words:
        return "CMP"
    if len(words) == 1:
        return _safe_code(words[0][:3], fallback="CMP", max_length=5)

    acronym = "".join(word[0] for word in words if word)
    return _safe_code(acronym, fallback="CMP", max_length=5)


def employer_folio_code(
    *,
    group_code: str | None = None,
    group_name: str | None = None,
    employer_name: str | None = None,
) -> str:
    """Prefer the canonical work-group code, otherwise derive a readable employer code."""
    explicit = _safe_code(group_code, fallback="", max_length=8)
    if explicit:
        return explicit

    source = group_name or employer_name
    normalized = " ".join(_normalized_words(source))
    if normalized in _GROUP_SPECIAL_CASES:
        return _GROUP_SPECIAL_CASES[normalized]

    words = [word for word in _normalized_words(source) if word not in _STOP_WORDS]
    if not words:
        return "GEN"
    if len(words) == 1:
        return _safe_code(words[0][:4], fallback="GEN", max_length=8)
    return _safe_code("".join(word[0] for word in words), fallback="GEN", max_length=8)


def assign_loan_folio(_mapper: Any, connection: Any, target: Any) -> None:
    """Assign one immutable, company/work-group scoped folio before a loan is inserted.

    A PostgreSQL transaction advisory lock serializes allocation inside each
    company/work-group sequence book, so concurrent loan creation cannot issue the
    same number. Existing folios are never rewritten.
    """
    if getattr(target, "folio_number", None):
        return

    company_name = connection.execute(
        text("SELECT name FROM loan_companies WHERE id = :company_id"),
        {"company_id": target.company_id},
    ).scalar_one()
    employer = connection.execute(
        text(
            """
            SELECT eg.code AS group_code, eg.name AS group_name, b.employer_name
            FROM borrowers AS b
            LEFT JOIN employer_groups AS eg ON eg.id = b.employer_group_id
            WHERE b.id = :borrower_id
            """
        ),
        {"borrower_id": target.borrower_id},
    ).mappings().one()

    company_code = company_folio_code(company_name)
    group_code = employer_folio_code(
        group_code=employer.get("group_code"),
        group_name=employer.get("group_name"),
        employer_name=employer.get("employer_name"),
    )

    lock_key = f"loan-folio:{target.company_id}:{group_code}"
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": lock_key},
    )
    next_sequence = connection.execute(
        text(
            """
            SELECT COALESCE(MAX(folio_sequence), 0) + 1
            FROM client_company_loan
            WHERE company_id = :company_id
              AND folio_group_code = :group_code
            """
        ),
        {"company_id": target.company_id, "group_code": group_code},
    ).scalar_one()

    target.folio_company_code = company_code
    target.folio_group_code = group_code
    target.folio_sequence = int(next_sequence)
    target.folio_number = f"{company_code}-{group_code}-{int(next_sequence):05d}"
