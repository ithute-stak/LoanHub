"""Confidential bank-submission CSV builder. Always generated on the server."""
from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
import re
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

GROUPS = {"FORCE": "force", "CIVIL": "civil", "SE": "s-e", "S/E": "s-e", "S-E": "s-e"}
BANK_ACCOUNT_LENGTHS = {"PB": 13, "STD": 13, "FNB": 11, "NB": 11}


def _group(value: object) -> str | None:
    text = str(value or "").strip().upper().replace(" ", "")
    return GROUPS.get(text)


def _bank(value: object) -> str:
    name = re.sub(r"\s+", " ", str(value or "").strip())
    if re.search(r"\b(FNB|FIRST NATIONAL BANK)\b", name, flags=re.IGNORECASE):
        return "FNB"
    upper = name.upper()
    if upper in {"LPB", "PB", "LESOTHO POSTBANK", "POSTBANK"}:
        return "PB"
    if upper in {"STD", "STANDARD BANK", "STANDARD LESOTHO BANK"}:
        return "STD"
    if upper in {"NB", "NEDBANK", "NEDBANK LESOTHO"}:
        return "NB"
    return upper


def _digits(value: object, *, min_length: int, max_length: int) -> str | None:
    raw = str(value or "").strip()
    if not re.fullmatch(r"[0-9]+", raw):
        return None
    return raw if min_length <= len(raw) <= max_length else None


def _client_name(name: object) -> str:
    """Surname and first initial; keep the initial within 10 characters."""
    value = re.sub(r"\\s+", " ", str(name or "").strip())
    value = re.sub(r"[^\\w .'-]", "", value, flags=re.UNICODE)
    parts = value.split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:10]
    if len(parts[-1].strip(".")) == 1:
        surname, initial = " ".join(parts[:-1]), parts[-1][0]
    else:
        surname, initial = parts[-1], parts[0][0]
    return f"{surname[:8]} {initial.upper()}"


def build_bank_submission_zip(records: list[dict], *, lender_name: str, employer_grouping: bool = False, include_spreadsheets: bool = False) -> tuple[bytes, dict]:
    """Return ZIP and non-PII outcome counts, never log or return account numbers.

    Bank A/B/C/D/E output is deliberately headerless, matching the bank
    sample. CSV has no native cell formats: recipient must import B and C as
    TEXT. Optional XLSX companions store those values as text and widen columns.
    """
    grouped: dict[str, list[tuple[str, str, str, str, str]]] = defaultdict(list)
    omitted = defaultdict(int)
    company = re.sub(r"[^\\w .'-]", "", str(lender_name or "").split(" ")[0])[:10].strip()
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
        bank = _bank(record.get("bank"))
        account = _digits(record.get("account"), min_length=1, max_length=20)
        if account and bank in BANK_ACCOUNT_LENGTHS:
            required_length = BANK_ACCOUNT_LENGTHS[bank]
            account = account.zfill(required_length) if len(account) <= required_length else None
        branch = _digits(record.get("branch"), min_length=1, max_length=6)
        name = _client_name(record.get("name"))
        if not bank or not account or not branch or not name:
            omitted["missing_or_invalid_bank_details"] += 1
            continue
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
            if include_spreadsheets:
                workbook = Workbook()
                sheet = workbook.active
                sheet.title = "Bank submission"
                sheet.freeze_panes = "A2"
                for row in rows:
                    sheet.append(row)
                for index, width in enumerate((19, 25, 13, 17, 20), start=1):
                    sheet.column_dimensions[get_column_letter(index)].width = width
                for cells in sheet.iter_rows():
                    for cell in cells:
                        cell.number_format = "@"  # Never coerce identifiers into numbers.
                        cell.alignment = Alignment(horizontal="left", vertical="center")
                        cell.font = Font(name="Aptos", size=11)
                    # Branch was already normalized to exactly six characters.
                    assert len(cells[2].value) == 6
                    sheet.row_dimensions[cells[0].row].height = 19
                workbook.calculation.fullCalcOnLoad = False
                spreadsheet = BytesIO()
                workbook.save(spreadsheet)
                archive.writestr(filename[:-4] + ".xlsx", spreadsheet.getvalue())
    return out.getvalue(), {
        "files": len(grouped),
        "rows": sum(len(rows) for rows in grouped.values()),
        "excluded": dict(omitted),
    }
