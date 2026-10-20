"""Read-only validation of historical CDAS transaction-log CSV exports.

This module never creates mandates, alters balances, or treats portal rows as
confirmed collections. The original export remains the source of truth.
"""
import csv
import io
from openpyxl import load_workbook
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
    "user_name": ("user name", "user_name"),
    "log_time": ("log time", "log_time"),
    "acd": ("acd", "action"),
}


def preview_cdas_history_csv(raw: bytes, filename: str = "history.csv") -> dict:
    if len(raw) > 2_000_000:
        raise ValueError("Historical CDAS file exceeds 2 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8; export again or convert to UTF-8 CSV") from exc
    reader = csv.DictReader(io.StringIO(text))
    return _preview_history_rows(reader)


def preview_cdas_history_file(raw: bytes, filename: str) -> dict:
    if len(raw) > 2_000_000:
        raise ValueError("Historical CDAS file exceeds 2 MB")
    if filename.lower().endswith(".csv"):
        return preview_cdas_history_csv(raw, filename)
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("Upload a CDAS CSV or Excel (.xlsx) export")
    try:
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheet = workbook.active
        if sheet is None:
            raise ValueError("Excel workbook contains no sheet")
        values = sheet.iter_rows(values_only=True)
        headings = next(values, None)
        if headings is None:
            raise ValueError("Excel sheet has no column headings")
        columns = [str(cell or "").strip() for cell in headings]
        def entries():
            for values_row in values:
                yield {key: value for key, value in zip(columns, values_row)}
        return _preview_history_rows(entries(), columns)
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError("Invalid CDAS Excel export: " + str(exc)) from exc
    finally:
        if "workbook" in locals():
            workbook.close()


def _preview_history_rows(reader, fieldnames=None) -> dict:
    headers = {str(h).strip().lower(): h for h in (fieldnames if fieldnames is not None else reader.fieldnames or []) if h}
    mapping = {name: next((headers[h] for h in variants if h in headers), None) for name, variants in FIELDS.items()}
    missing = [name for name, column in mapping.items() if column is None and name not in ("user_name", "log_time", "acd")]
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
        record = {key: str(row.get(column) if row.get(column) is not None else "").strip() if column else "" for key, column in mapping.items()}
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
               record["ending_month"], record["monthly_amount"], record["principal_amount"], record["log_time"], record["acd"])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        rows.append(record)
    return {"source": "historical_cdas_csv_preview", "persisted": False,
            "rows": rows, "valid_count": len(rows), "duplicate_count": duplicates,
            "invalid_count": len(invalid), "errors": invalid[:100], "truncated_errors": len(invalid) > 100}


def reconcile_preview_rows(rows: list[dict], mandates: list[dict]) -> dict:
    """Conservative reconciliation: never infer a borrower from names or amounts.

    Mandate candidates must have exact employee and reference identifiers.
    Ambiguous or mismatched candidates remain for human review.
    """
    index: dict[tuple[str, str], list[dict]] = {}
    employee_index: dict[str, list[dict]] = {}
    for mandate in mandates:
        employee = str(mandate.get("employee_no") or "").strip()
        if not employee:
            continue
        employee_index.setdefault(employee, []).append(mandate)
        for reference in (mandate.get("mandate_number"), mandate.get("external_reference")):
            ref = str(reference or "").strip()
            if ref:
                index.setdefault((employee, ref), []).append(mandate)

    decisions = []
    counts = {"exact_match": 0, "conflict": 0, "unmatched": 0, "manual_review": 0}
    for row in rows:
        employee = row["employee_no"].strip()
        reference = row["policy_reference"].strip()
        candidates = list({str(m["id"]): m for m in index.get((employee, reference), [])}.values())
        if len(candidates) == 1:
            candidate = candidates[0]
            if Decimal(str(candidate["monthly_amount"])) != Decimal(row["monthly_amount"].replace(",", "")):
                status = "conflict"
                reason = "Exact identifiers match but monthly amounts differ"
            else:
                status = "exact_match"
                reason = "Employee, reference and monthly amount agree; review before accepting"
            matched_id = str(candidate["id"])
        elif len(candidates) > 1:
            status, reason, matched_id = "manual_review", "Multiple mandates match both identifiers", None
        elif employee in employee_index:
            status, reason, matched_id = "manual_review", "Employee exists, but policy reference does not match", None
        else:
            status, reason, matched_id = "unmatched", "No matching LoanHub employee record", None
        counts[status] += 1
        decisions.append({"employee_no": employee, "policy_reference": reference,
                          "status": status, "reason": reason, "matched_mandate_id": matched_id})
    return {"persisted": False, "counts": counts, "decisions": decisions}
