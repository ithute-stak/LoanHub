"""Parse legacy bank CSV imports without changing stored records."""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from io import StringIO, BytesIO
from openpyxl import load_workbook
import re

MAX_ROWS = 5000


def parse_legacy_csv(data: bytes, *, known_groups: dict[str, str], selected_group: str | None = None) -> tuple[list[dict], list[dict]]:
    if len(data) > 2_000_000:
        raise ValueError("CSV exceeds 2 MB")
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8") from exc
    reader = csv.reader(StringIO(decoded, newline=""))
    valid, issues = [], []
    for index, cells in enumerate(reader, 1):
        if index > MAX_ROWS:
            raise ValueError("CSV exceeds 5000 rows")
        if not cells or not any(x.strip() for x in cells):
            continue
        if index == 1 and [x.strip().lower() for x in cells[:5]] == [
            "work group", "client name", "account number", "branch code", "amount"
        ]:
            continue
        if selected_group is not None and index == 1 and [x.strip().lower() for x in cells[:3]] == ["client name", "account number", "amount"]:
            continue
        if selected_group is not None and index == 1 and [x.strip().lower() for x in cells[:4]] == ["client name", "account number", "amount", "employer"]:
            continue
        if selected_group is not None and len(cells) == 4:
            group = selected_group
            name, account, amount, employer = (cell.strip() for cell in cells)
            branch = ""
        elif selected_group is not None and len(cells) == 3:
            group = selected_group
            name, account, amount = (cell.strip() for cell in cells)
            branch = ""
            employer = ""
        elif len(cells) == 6:
            group, name, account, branch, amount, employer = (cell.strip() for cell in cells)
        elif len(cells) == 5:
            group, name, account, branch, amount = (cell.strip() for cell in cells)
            employer = ""
        else:
            issues.append({"row": index, "reason": "Expected Client name, Account number, Amount, Employer (4 columns)"})
            continue
        group_id = known_groups.get(group.casefold())
        try:
            value = Decimal(amount)
        except (InvalidOperation, ValueError):
            value = Decimal("NaN")
        if not group_id:
            reason = "Unknown work group"
        elif not employer or len(employer) > 120:
            reason = "Employer is required (1-120 characters)"
        elif not name or len(name) > 120:
            reason = "Invalid client name"
        elif not re.fullmatch(r"[0-9]{6,20}", account):
            reason = "Account must contain 6-20 digits"
        elif branch and not re.fullmatch(r"[0-9]{1,6}", branch):
            reason = "Branch must contain 1-6 digits"
        elif not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2 or value >= Decimal("10000000000000"):
            reason = "Invalid deduction amount"
        else:
            reason = None
        if reason:
            issues.append({"row": index, "reason": reason})
        else:
            valid.append(dict(row=index, group_id=group_id, name=name,
                              account=account, branch=branch.zfill(6) if branch else "", amount=value, employer=employer))
    return valid, issues


def parse_legacy_spreadsheet(data: bytes, *, known_groups: dict[str, str], selected_group: str | None = None):
    """Convert the first worksheet into CSV for the shared strict parser."""
    if len(data) > 2_000_000:
        raise ValueError("Spreadsheet exceeds 2 MB")
    try:
        book = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("Invalid XLSX file") from exc
    try:
        buffer = StringIO(newline="")
        writer = csv.writer(buffer)
        sheet = book.active
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if cell is None else str(cell).strip() for cell in row]
            while cells and not cells[-1]:
                cells.pop()
            writer.writerow(cells)
        return parse_legacy_csv(buffer.getvalue().encode("utf-8"), known_groups=known_groups, selected_group=selected_group)
    finally:
        book.close()
