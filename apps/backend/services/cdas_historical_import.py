"""Read-only validation of historical CDAS transaction-log CSV exports.

This module never creates mandates, alters balances, or treats portal rows as
confirmed collections. The original export remains the source of truth.
"""
import csv
import io
from decimal import Decimal, InvalidOperation

MAX_ROWS = 5000
FIELDS = {
    "employee_no": ("employee no", "employee number", "employee_no"),
    "employee_name": ("employee name", "employee_name"),
    "monthly_amount": ("monthly amount", "monthly_amount"),
    "total_installment": ("total installment", "total installments", "total_installment"),
    "principal_amount": ("principal amount", "principal_amount"),
    "starting_month": ("starting month", "starting_month"),
    "ending_month": ("ending month", "ending_month"),
    "policy_reference": ("policy ref. no", "policy ref no", "policy reference", "policy_ref_no"),
}


def preview_cdas_history_csv(raw: bytes) -> dict:
    if len(raw) > 2_000_000:
        raise ValueError("Historical CDAS file exceeds 2 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8; export again or convert to UTF-8 CSV") from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = {str(h).strip().lower(): h for h in (reader.fieldnames or []) if h}
    mapping = {name: next((headers[h] for h in variants if h in headers), None) for name, variants in FIELDS.items()}
    missing = [name for name, column in mapping.items() if column is None]
    if missing:
        raise ValueError("Missing CDAS columns: " + ", ".join(missing))
    rows = []
    invalid = []
    seen = set()
    duplicates = 0
    for line, row in enumerate(reader, start=2):
        if line > MAX_ROWS + 1:
            raise ValueError("CSV exceeds the 5000-row preview limit")
        if None in row:
            invalid.append({"line": line, "reason": "Malformed CSV row"})
            continue
        record = {key: str(row[column] or "").strip() for key, column in mapping.items()}
        if not record["employee_no"] or not record["policy_reference"]:
            invalid.append({"line": line, "reason": "Employee number and policy reference are required"})
            continue
        try:
            monthly = Decimal(record["monthly_amount"].replace(",", ""))
            principal = Decimal(record["principal_amount"].replace(",", ""))
            installments = int(record["total_installment"])
            if monthly < 0 or principal < 0 or installments < 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            invalid.append({"line": line, "reason": "Invalid numeric amount or installment count"})
            continue
        key = (record["employee_no"], record["policy_reference"], record["starting_month"],
               record["ending_month"], record["monthly_amount"], record["principal_amount"])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        rows.append(record)
    return {"source": "historical_cdas_csv_preview", "persisted": False,
            "rows": rows, "valid_count": len(rows), "duplicate_count": duplicates,
            "invalid_count": len(invalid), "errors": invalid[:100], "truncated_errors": len(invalid) > 100}
