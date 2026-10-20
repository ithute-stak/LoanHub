"""Confidential bank-submission CSV builder. Always generated on the server."""
from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
import re
from zipfile import ZIP_DEFLATED, ZipFile

GROUPS = {"FORCE": "force", "CIVIL": "civil", "SE": "s-e", "S/E": "s-e", "S-E": "s-e"}
BANK_ACCOUNT_LENGTHS = {
    # Generic conservative bounds; bank-specific validation belongs to the
    # bank mandate validator when authoritative rules are supplied.
    "default": (6, 20),
}


def _group(value: object) -> str | None:
    text = str(value or "").strip().upper().replace(" ", "")
    return GROUPS.get(text)


def _bank(value: object) -> str:
    name = re.sub(r"\s+", " ", str(value or "").strip())
    if re.search(r"\b(FNB|FIRST NATIONAL BANK)\b", name, flags=re.IGNORECASE):
        return "FNB"
    return name.upper()



def _bank_from_account(account: str) -> str:
    """Company-specified Lesotho account prefix routing, not bank verification."""
    if account.startswith(("62", "63", "6")):
        return "FNB"
    if account.startswith("90"):
        return "STD"
    if account.startswith("10"):
        return "LPS"
    return "NB"


def _digits(value: object, *, min_length: int, max_length: int) -> str | None:
    raw = str(value or "").strip()
    if not re.fullmatch(r"[0-9]+", raw):
        return None
    return raw if min_length <= len(raw) <= max_length else None


def _client_name(name: object) -> str:
    # Strictly fewer than 11 characters; never allow spreadsheet formula text.
    value = re.sub(r"\s+", " ", str(name or "").strip())
    value = re.sub(r"[^\w .'-]", "", value, flags=re.UNICODE)
    return value[:10].strip()


def build_bank_submission_zip(records: list[dict], *, lender_name: str, employer_grouping: bool = False) -> tuple[bytes, dict]:
    """Return ZIP and non-PII outcome counts, never log or return account numbers.

    Bank A/B/C/D/E output is deliberately headerless, matching the bank
    sample. CSV has no native Excel data types: recipient must import B and C
    as TEXT to retain leading zeros.
    """
    grouped: dict[str, list[tuple[str, str, str, str, str]]] = defaultdict(list)
    omitted = defaultdict(int)
    company = _client_name(str(lender_name or "").split(" ")[0])
    if not company:
        raise ValueError("Lending company name is missing")
    for record in records:
        try:
            balance = Decimal(str(record.get("balance", "0")))
            installment = Decimal(str(record.get("installment", "0")))
        except (ValueError, TypeError, InvalidOperation):
            omitted["invalid_amount"] += 1
            continue
        if not balance.is_finite() or not installment.is_finite() or balance <= 0 or installment <= 0:
            omitted["not_collectible"] += 1
            continue
        group = _group(record.get("group"))
        if not group:
            omitted["unknown_work_group"] += 1
            continue
        account = _digits(record.get("account"), min_length=6, max_length=20)
        branch = _digits(record.get("branch"), min_length=1, max_length=6)
        name = _client_name(record.get("name"))
        if not account or not branch or not name:
            omitted["missing_or_invalid_bank_details"] += 1
            continue
        bank = _bank_from_account(account)
        # A remaining balance smaller than a standard installment must not
        # result in an over-collection instruction.
        amount = min(balance, installment).quantize(Decimal("0.01"))
        if amount <= 0:
            omitted["not_collectible"] += 1
            continue
        custom_filename = record.get("custom_filename")
        if custom_filename:
            if not isinstance(custom_filename, str) or not re.fullmatch(r"CUSTOM-[A-Za-z0-9_-]{1,100}\\.csv", custom_filename):
                omitted["invalid_custom_group"] += 1
                continue
            filename = custom_filename
        elif employer_grouping:
            employer = re.sub(r"\\s+", " ", str(record.get("employer") or "").strip())
            if not employer or len(employer) > 120:
                omitted["missing_employer"] += 1
                continue
            employer_slug = re.sub(r"[^A-Z0-9]+", "-", employer.upper()).strip("-")[:50]
            if not employer_slug:
                omitted["missing_employer"] += 1
                continue
            bank_name = {"STD": "STANDARD-BANK", "PB": "POSTBANK", "NB": "NEDBANK", "FNB": "FNB"}.get(bank, bank)
            bank_slug = re.sub(r"[^A-Z0-9]+", "-", bank_name.upper()).strip("-")[:40]
            filename = f"{bank_slug}-{branch.zfill(6)}-{group}.csv" if bank == "FNB" else f"{bank_slug}-{branch.zfill(6)}-{group}-{employer_slug}.csv"
        else:
            filename = "FNB-all-groups.csv" if bank == "FNB" else (
                f"{re.sub(r'[^A-Z0-9]+', '-', bank).strip('-')[:40]}-{group}.csv"
            )
        grouped[filename].append((name, account, branch.zfill(6), f"{amount:.2f}", company))
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        for filename, rows in sorted(grouped.items()):
            stream = StringIO(newline="")
            writer = csv.writer(stream, lineterminator="\r\n", quoting=csv.QUOTE_ALL)
            writer.writerows(rows)
            archive.writestr(filename, stream.getvalue().encode("utf-8"))
    return out.getvalue(), {
        "files": len(grouped),
        "rows": sum(len(rows) for rows in grouped.values()),
        "excluded": dict(omitted),
    }
