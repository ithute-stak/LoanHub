"""Parse legacy bank CSV imports without changing stored records."""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from io import StringIO
import re

MAX_ROWS = 5000


def parse_legacy_csv(data: bytes, *, known_groups: dict[str, str]) -> tuple[list[dict], list[dict]]:
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
        if len(cells) != 5:
            issues.append({"row": index, "reason": "Expected 5 columns"})
            continue
        group, name, account, branch, amount = (cell.strip() for cell in cells)
        group_id = known_groups.get(group.casefold())
        try:
            value = Decimal(amount)
        except (InvalidOperation, ValueError):
            value = Decimal("NaN")
        if not group_id:
            reason = "Unknown work group"
        elif not name or len(name) > 120:
            reason = "Invalid client name"
        elif not re.fullmatch(r"[0-9]{6,20}", account):
            reason = "Account must contain 6-20 digits"
        elif not re.fullmatch(r"[0-9]{1,6}", branch):
            reason = "Branch must contain 1-6 digits"
        elif not value.is_finite() or value <= 0 or value.as_tuple().exponent < -2 or value >= Decimal("10000000000000"):
            reason = "Invalid deduction amount"
        else:
            reason = None
        if reason:
            issues.append({"row": index, "reason": reason})
        else:
            valid.append(dict(row=index, group_id=group_id, name=name,
                              account=account, branch=branch.zfill(6), amount=value))
    return valid, issues
