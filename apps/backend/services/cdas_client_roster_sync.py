from __future__ import annotations

import base64
import csv
import hashlib
import io
import re
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from database.models.origination import OriginationIntegrationConfiguration
from integrations.cdas import CdasDocumentType, CdasError
from services.cdas_analysis_history import save_or_get_analysis_record
from services.cdas_config_service import CDAS_PROVIDER, get_company_cdas_client
from services.cdas_monthly_automation import local_now


ROSTER_SYNC_KEY = "client_roster_sync"
ROSTER_SOURCE = "CDAS_PROVIDER_ROSTER_SYNC"
DEFAULT_BOOTSTRAP_LOOKBACK_MONTHS = 24
DEFAULT_DAILY_LOOKBACK_MONTHS = 2
MAX_BOOTSTRAP_LOOKBACK_MONTHS = 60
DAILY_SYNC_TIME = time(hour=3, minute=45)

_EMPLOYEE_HEADERS = {
    "employeeno",
    "employeenumber",
    "employeeid",
    "staffno",
    "staffnumber",
    "payrollno",
    "payrollnumber",
    "personnelno",
    "personnelnumber",
}
_FULL_NAME_HEADERS = {"clientname", "employeename", "fullname", "name"}
_FIRST_NAME_HEADERS = {"firstname", "firstnames", "givenname", "givennames"}
_SURNAME_HEADERS = {"surname", "lastname", "familyname"}
_NID_HEADERS = {"nationalid", "nationalidnumber", "idnumber", "idno", "nid"}
_EMPLOYER_HEADERS = {"employer", "employername", "department", "ministry"}
_AMOUNT_HEADERS = {
    "amount",
    "deductionamount",
    "monthlydeduction",
    "monthlydeductionamount",
    "collectionamount",
    "installmentamount",
    "instalmentamount",
}
_STATUS_HEADERS = {"status", "deductionstatus"}
_REFERENCE_HEADERS = {"reference", "referenceno", "referencenumber", "deductionreference", "deductionid"}


class CdasRosterDocumentError(ValueError):
    """Raised when a CDAS output file cannot be parsed safely."""


def _utc_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _normalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _first_value(row: dict[str, Any], aliases: set[str]) -> str:
    for key, value in row.items():
        if _normalize_header(key) in aliases:
            cleaned = _clean_text(value)
            if cleaned:
                return cleaned
    return ""


def _parse_decimal(value: Any) -> Decimal | None:
    text = _clean_text(value)
    if not text:
        return None
    text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def _looks_like_text(data: bytes) -> bool:
    if not data:
        return False
    if data.startswith(b"PK\x03\x04"):
        return True
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError:
            return False
    return "\n" in text or any(delimiter in text for delimiter in (",", ";", "\t", "|"))


def _decode_document_content(document: dict[str, Any]) -> bytes:
    content = document.get("Content")
    if content is None:
        content = document.get("content")
    if content is None:
        raise CdasRosterDocumentError("CDAS output file did not contain Content")

    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)
    if isinstance(content, list) and all(isinstance(item, int) and 0 <= item <= 255 for item in content):
        return bytes(content)
    if isinstance(content, dict):
        values = content.get("data") or content.get("Data")
        if isinstance(values, list) and all(isinstance(item, int) and 0 <= item <= 255 for item in values):
            return bytes(values)
        raise CdasRosterDocumentError("CDAS output file Content used an unsupported object format")
    if not isinstance(content, str):
        raise CdasRosterDocumentError("CDAS output file Content used an unsupported format")

    value = content.strip()
    if not value:
        raise CdasRosterDocumentError("CDAS output file Content was empty")
    if value.startswith("data:") and "," in value:
        metadata, value = value.split(",", 1)
        if ";base64" not in metadata.lower():
            return value.encode("utf-8")

    compact = re.sub(r"\s+", "", value)
    if len(compact) >= 16:
        padded = compact + ("=" * (-len(compact) % 4))
        try:
            decoded = base64.b64decode(padded, validate=True)
            if _looks_like_text(decoded):
                return decoded
        except (ValueError, base64.binascii.Error):
            pass
    return value.encode("utf-8")


def _find_header_row(rows: list[list[Any]]) -> tuple[int, list[str]]:
    for index, values in enumerate(rows[:25]):
        normalized = [_normalize_header(value) for value in values]
        if any(value in _EMPLOYEE_HEADERS for value in normalized):
            return index, [_clean_text(value) for value in values]
    raise CdasRosterDocumentError(
        "CDAS output file does not expose a recognised employee-number header; import was stopped rather than guessing columns"
    )


def _rows_from_workbook(data: bytes) -> list[dict[str, Any]]:
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise CdasRosterDocumentError("CDAS output file could not be opened as an Excel workbook") from exc
    try:
        for sheet in workbook.worksheets:
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
            if not rows:
                continue
            try:
                header_index, headers = _find_header_row(rows)
            except CdasRosterDocumentError:
                continue
            return [
                {headers[column]: value for column, value in enumerate(values) if column < len(headers) and headers[column]}
                for values in rows[header_index + 1 :]
                if any(_clean_text(value) for value in values)
            ]
    finally:
        workbook.close()
    raise CdasRosterDocumentError("No worksheet contained a recognised employee-number header")


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _rows_from_delimited_text(data: bytes) -> list[dict[str, Any]]:
    text = _decode_text(data)
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error as exc:
        raise CdasRosterDocumentError("CDAS output file delimiter could not be identified safely") from exc
    matrix = [list(row) for row in csv.reader(io.StringIO(text), dialect)]
    header_index, headers = _find_header_row(matrix)
    return [
        {headers[column]: value for column, value in enumerate(values) if column < len(headers) and headers[column]}
        for values in matrix[header_index + 1 :]
        if any(_clean_text(value) for value in values)
    ]


def parse_cdas_output_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse one provider Output File without relying on undocumented column positions."""
    data = _decode_document_content(document)
    filename = _clean_text(document.get("FileName") or document.get("fileName") or document.get("filename")).lower()
    if data.startswith(b"PK\x03\x04") or filename.endswith((".xlsx", ".xlsm")):
        return _rows_from_workbook(data)
    if filename.endswith(".xls"):
        raise CdasRosterDocumentError("Legacy .xls CDAS output files are not supported safely; use CSV or XLSX")
    return _rows_from_delimited_text(data)


def _profile_from_row(row: dict[str, Any]) -> dict[str, str]:
    employee_no = _first_value(row, _EMPLOYEE_HEADERS)
    full_name = _first_value(row, _FULL_NAME_HEADERS)
    if not full_name:
        first = _first_value(row, _FIRST_NAME_HEADERS)
        surname = _first_value(row, _SURNAME_HEADERS)
        full_name = " ".join(value for value in (first, surname) if value).strip()
    return {
        "employee_no": employee_no,
        "full_name": full_name,
        "nid": _first_value(row, _NID_HEADERS),
        "employer": _first_value(row, _EMPLOYER_HEADERS),
    }


def _merge_profile(target: dict[str, str], candidate: dict[str, str]) -> None:
    for field in ("full_name", "nid", "employer"):
        if candidate.get(field):
            target[field] = candidate[field]


def _group_document_rows(
    rows: list[dict[str, Any]],
    *,
    year: int,
    month: int,
    file_name: str,
    content_sha256: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        profile = _profile_from_row(row)
        employee_no = profile["employee_no"].strip()
        if not employee_no:
            continue
        item = grouped.setdefault(
            employee_no,
            {
                "profile": profile,
                "row_count": 0,
                "total_monthly_deductions": Decimal("0.00"),
                "amount_values_seen": 0,
                "references": set(),
                "statuses": set(),
                "year": year,
                "month": month,
                "file_name": file_name,
                "content_sha256": content_sha256,
            },
        )
        _merge_profile(item["profile"], profile)
        item["row_count"] += 1
        amount_text = _first_value(row, _AMOUNT_HEADERS)
        amount = _parse_decimal(amount_text)
        if amount is not None:
            item["total_monthly_deductions"] += amount
            item["amount_values_seen"] += 1
        reference = _first_value(row, _REFERENCE_HEADERS)
        if reference:
            item["references"].add(reference)
        status = _first_value(row, _STATUS_HEADERS)
        if status:
            item["statuses"].add(status)
    return grouped


def _months_ending_at(value: date, count: int) -> list[tuple[int, int]]:
    count = max(1, count)
    months: list[tuple[int, int]] = []
    year, month = value.year, value.month
    for _ in range(count):
        months.append((year, month))
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    months.reverse()
    return months


def _bounded_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)


def get_roster_sync_state(row: OriginationIntegrationConfiguration) -> dict[str, Any]:
    root = dict(row.configuration) if isinstance(row.configuration, dict) else {}
    value = root.get(ROSTER_SYNC_KEY)
    return dict(value) if isinstance(value, dict) else {}


def _write_roster_sync_state(
    db: Session,
    row: OriginationIntegrationConfiguration,
    updates: dict[str, Any],
) -> dict[str, Any]:
    root = dict(row.configuration) if isinstance(row.configuration, dict) else {}
    state = dict(root.get(ROSTER_SYNC_KEY)) if isinstance(root.get(ROSTER_SYNC_KEY), dict) else {}
    state.update(updates)
    root[ROSTER_SYNC_KEY] = state
    row.configuration = root
    db.add(row)
    db.commit()
    db.refresh(row)
    return state


def _configuration_lookbacks(row: OriginationIntegrationConfiguration) -> tuple[int, int]:
    state = get_roster_sync_state(row)
    bootstrap = _bounded_int(
        state.get("bootstrap_lookback_months"),
        DEFAULT_BOOTSTRAP_LOOKBACK_MONTHS,
        minimum=1,
        maximum=MAX_BOOTSTRAP_LOOKBACK_MONTHS,
    )
    daily = _bounded_int(
        state.get("daily_lookback_months"),
        DEFAULT_DAILY_LOOKBACK_MONTHS,
        minimum=1,
        maximum=6,
    )
    return bootstrap, daily


def _analysis_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    profile = item["profile"]
    total = item["total_monthly_deductions"]
    return {
        "source": ROSTER_SOURCE,
        "decision": "CDAS_IMPORTED",
        "status": "IMPORTED",
        "profile": {
            "employee_no": profile.get("employee_no") or "",
            "full_name": profile.get("full_name") or "",
            "nid": profile.get("nid") or "",
            "employer": profile.get("employer") or "",
        },
        "reported_active_monthly_deductions": str(total),
        "total_monthly_deductions": str(total),
        "data_quality_issue_count": 0 if item["amount_values_seen"] else 1,
        "cdas_roster_sync": {
            "document_type": int(CdasDocumentType.OUTPUT_FILE),
            "year": item["year"],
            "month": item["month"],
            "file_name": item["file_name"],
            "content_sha256": item["content_sha256"],
            "row_count": item["row_count"],
            "amount_values_seen": item["amount_values_seen"],
            "references": sorted(item["references"]),
            "statuses": sorted(item["statuses"]),
        },
    }


async def sync_company_cdas_roster(
    db: Session,
    *,
    row: OriginationIntegrationConfiguration,
    mode: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Import the agency roster from CDAS Output Files into LoanHub client history."""
    if mode not in {"bootstrap", "daily"}:
        raise ValueError("CDAS roster sync mode must be bootstrap or daily")
    current = now or local_now()
    bootstrap_lookback, daily_lookback = _configuration_lookbacks(row)
    lookback = bootstrap_lookback if mode == "bootstrap" else daily_lookback
    started_at = _utc_iso()
    _write_roster_sync_state(
        db,
        row,
        {
            "last_started_at": started_at,
            "last_mode": mode,
            "last_status": "running",
            "last_error": None,
        },
    )

    client = get_company_cdas_client(db, row.company_id)
    latest_by_employee: dict[str, dict[str, Any]] = {}
    documents_scanned = 0
    document_errors: list[str] = []

    for year, month in _months_ending_at(current.date(), lookback):
        try:
            document = await client.get_document(
                year=year,
                month=month,
                document_type=int(CdasDocumentType.OUTPUT_FILE),
            )
            if not isinstance(document, dict):
                raise CdasRosterDocumentError("CDAS get_document returned a non-object response")
            rows = parse_cdas_output_document(document)
            raw = _decode_document_content(document)
            file_name = _clean_text(document.get("FileName") or document.get("fileName") or document.get("filename"))
            grouped = _group_document_rows(
                rows,
                year=year,
                month=month,
                file_name=file_name,
                content_sha256=hashlib.sha256(raw).hexdigest(),
            )
            documents_scanned += 1
            for employee_no, item in grouped.items():
                latest_by_employee[employee_no] = item
        except (CdasError, CdasRosterDocumentError, UnicodeError, csv.Error) as exc:
            document_errors.append(f"{year:04d}-{month:02d}: {exc}")

    if documents_scanned == 0:
        error = "No CDAS Output File could be fetched and parsed safely"
        if document_errors:
            error = f"{error}. {document_errors[-1]}"
        _write_roster_sync_state(
            db,
            row,
            {
                "last_completed_at": _utc_iso(),
                "last_status": "failed",
                "last_error": error[:1000],
                "documents_scanned": 0,
                "clients_seen": 0,
                "records_created": 0,
            },
        )
        return {
            "company_id": str(row.company_id),
            "mode": mode,
            "status": "failed",
            "documents_scanned": 0,
            "clients_seen": 0,
            "records_created": 0,
            "document_errors": document_errors,
        }

    records_created = 0
    for employee_no, item in latest_by_employee.items():
        profile = item["profile"]
        _record, created = save_or_get_analysis_record(
            db,
            company_id=row.company_id,
            analyzed_by_user_id=None,
            analyzed_by_name="CDAS scheduled roster sync",
            analyzed_by_role="SYSTEM",
            client_name=profile.get("full_name") or None,
            client_reference=f"CDAS:{employee_no}",
            analysis=_analysis_snapshot(item),
        )
        records_created += int(created)

    status = "partial" if document_errors else "success"
    updates: dict[str, Any] = {
        "last_completed_at": _utc_iso(),
        "last_status": status,
        "last_error": ("; ".join(document_errors[-3:])[:1000] if document_errors else None),
        "documents_scanned": documents_scanned,
        "clients_seen": len(latest_by_employee),
        "records_created": records_created,
    }
    if mode == "bootstrap":
        updates["bootstrap_completed_at"] = _utc_iso()
        # If deployment/bootstrap occurs after today's 03:45 boundary, the
        # bootstrap itself is today's roster refresh. The next scheduled read
        # is therefore the following 03:45, not another immediate duplicate.
        if current.timetz().replace(tzinfo=None) >= DAILY_SYNC_TIME:
            updates["last_scheduled_run_date"] = current.date().isoformat()
    else:
        updates["last_scheduled_run_date"] = current.date().isoformat()

    _write_roster_sync_state(db, row, updates)
    return {
        "company_id": str(row.company_id),
        "mode": mode,
        "status": status,
        "documents_scanned": documents_scanned,
        "clients_seen": len(latest_by_employee),
        "records_created": records_created,
        "document_errors": document_errors,
    }


def _enabled_cdas_configurations(db: Session) -> list[OriginationIntegrationConfiguration]:
    return (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
            OriginationIntegrationConfiguration.is_enabled.is_(True),
        )
        .all()
    )


def _daily_due(state: dict[str, Any], now: datetime) -> bool:
    if now.timetz().replace(tzinfo=None) < DAILY_SYNC_TIME:
        return False
    return str(state.get("last_scheduled_run_date") or "") != now.date().isoformat()


async def run_cdas_client_roster_sync_cycle(
    db: Session,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Bootstrap each enabled company once, then refresh it once per day after 03:45."""
    current = now or local_now()
    results: list[dict[str, Any]] = []
    for row in _enabled_cdas_configurations(db):
        state = get_roster_sync_state(row)
        try:
            if not state.get("bootstrap_completed_at"):
                results.append(await sync_company_cdas_roster(db, row=row, mode="bootstrap", now=current))
                continue
            if _daily_due(state, current):
                results.append(await sync_company_cdas_roster(db, row=row, mode="daily", now=current))
        except Exception as exc:
            # Keep one company's provider/configuration problem from blocking
            # every other tenant. Persist a bounded operational error for the UI.
            db.rollback()
            try:
                _write_roster_sync_state(
                    db,
                    row,
                    {
                        "last_completed_at": _utc_iso(),
                        "last_status": "failed",
                        "last_error": str(exc)[:1000],
                    },
                )
            except Exception:
                db.rollback()
            results.append(
                {
                    "company_id": str(row.company_id),
                    "mode": "bootstrap" if not state.get("bootstrap_completed_at") else "daily",
                    "status": "failed",
                    "error": str(exc),
                }
            )
    return results
