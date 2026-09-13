from __future__ import annotations

import re
from datetime import date
from typing import Iterable


_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_KNOWN_STATUSES = {
    "active",
    "inactive",
    "stopped",
    "expired",
    "cancelled",
    "canceled",
    "suspended",
    "closed",
}

_FLAT_ROW_PATTERN = re.compile(
    r"^\s*(?P<item_code>\d{3,8})\s+"
    r"(?P<agency>.+?)\s+"
    r"(?:(?P<sequence>\d+)\s+)?"
    r"(?:M|LSL)\s*(?P<amount>[\d][\d,\s]*(?:\.\d{1,2})?)\s+"
    r"(?P<effective>\d{4}-[A-Za-z]{3})\s+"
    r"(?P<expiry>\d{4}-[A-Za-z]{3})\s+"
    r"(?P<reference>.+?)\s+"
    r"(?P<status>Active|Inactive|Stopped|Expired|Cancelled|Canceled|Suspended|Closed)\s*$",
    re.IGNORECASE,
)


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _parse_month(value: str) -> date:
    match = re.fullmatch(r"(\d{4})-([A-Za-z]{3})", value.strip())
    if not match:
        raise ValueError(f"Unsupported CDAS month: {value}")
    month = _MONTHS.get(match.group(2).lower())
    if not month:
        raise ValueError(f"Unsupported CDAS month: {value}")
    return date(int(match.group(1)), month, 1)


def _month_diff(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _parse_amount(value: str) -> float:
    match = re.search(r"(?:M|LSL)?\s*([\d][\d,\s]*(?:\.\d{1,2})?)", value, re.IGNORECASE)
    if not match:
        raise ValueError(f"Unsupported CDAS amount: {value}")
    return float(match.group(1).replace(",", "").replace(" ", ""))


def _parse_pipe_row(line: str) -> dict | None:
    cells = [cell.strip() for cell in line.split("|")]
    cells = [cell for cell in cells if cell and not re.fullmatch(r"-+", cell)]
    if not cells:
        return None

    date_indexes = [
        index for index, cell in enumerate(cells) if re.fullmatch(r"\d{4}-[A-Za-z]{3}", cell)
    ]
    if len(date_indexes) < 2:
        return None
    effective_index, expiry_index = date_indexes[0], date_indexes[1]

    item_index = next(
        (
            index
            for index, cell in enumerate(cells[:effective_index])
            if re.fullmatch(r"\d{3,8}", cell)
        ),
        None,
    )
    if item_index is None:
        return None

    amount_index = next(
        (
            index
            for index, cell in enumerate(cells[item_index + 1 : effective_index], item_index + 1)
            if re.search(r"(?:M|LSL)\s*[\d,]+", cell, re.IGNORECASE)
        ),
        None,
    )
    if amount_index is None:
        return None

    status_index = next(
        (
            index
            for index in range(len(cells) - 1, expiry_index, -1)
            if cells[index].lower() in _KNOWN_STATUSES
        ),
        None,
    )
    if status_index is None:
        return None

    agency_cells = cells[item_index + 1 : amount_index]
    if agency_cells and re.fullmatch(r"\d+", agency_cells[-1]):
        agency_cells = agency_cells[:-1]
    agency = " ".join(agency_cells).strip()
    if not agency:
        return None

    return {
        "item_code": cells[item_index],
        "agency_name": agency,
        "deduction_amount": _parse_amount(cells[amount_index]),
        "effective_date": _parse_month(cells[effective_index]),
        "expiry_date": _parse_month(cells[expiry_index]),
        "reference_no": " ".join(cells[expiry_index + 1 : status_index]).strip(),
        "status": cells[status_index].strip().title(),
    }


def _parse_flat_row(line: str) -> dict | None:
    match = _FLAT_ROW_PATTERN.match(line)
    if not match:
        return None
    return {
        "item_code": match.group("item_code"),
        "agency_name": match.group("agency").strip(),
        "deduction_amount": _parse_amount(match.group("amount")),
        "effective_date": _parse_month(match.group("effective")),
        "expiry_date": _parse_month(match.group("expiry")),
        "reference_no": match.group("reference").strip(),
        "status": match.group("status").strip().title(),
    }


def parse_cdas_text(raw_text: str) -> list[dict]:
    """Parse CDAS rows copied from a table, markdown table, or plain text list."""
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for raw_line in raw_text.replace("\u00a0", " ").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = _parse_pipe_row(line) if "|" in line else _parse_flat_row(line)
        if not parsed:
            continue
        key = (
            parsed["item_code"],
            parsed["reference_no"],
            parsed["expiry_date"].isoformat(),
        )
        if key not in seen:
            seen.add(key)
            rows.append(parsed)

    if not rows:
        raise ValueError(
            "No CDAS deduction rows were recognised. Paste the deduction rows with item code, "
            "agency, amount, effective month, expiry month, reference and status."
        )
    return rows


def _is_own_booking(row: dict, own_item_codes: set[str], own_agencies: set[str]) -> bool:
    return row["item_code"].strip() in own_item_codes or _normalise(row["agency_name"]) in own_agencies


def _serialise_row(
    row: dict,
    *,
    as_of: date,
    booking_lead_months: int,
    own_item_codes: set[str],
    own_agencies: set[str],
) -> dict:
    effective = row["effective_date"]
    expiry = row["expiry_date"]
    as_of_month = date(as_of.year, as_of.month, 1)
    booking_open = _shift_month(expiry, -booking_lead_months)
    active = row["status"].lower() == "active"
    is_own = _is_own_booking(row, own_item_codes, own_agencies)

    elapsed = max(0, _month_diff(effective, as_of_month))
    months_to_expiry = max(0, _month_diff(as_of_month, expiry))
    scheduled_deduction_months = max(1, _month_diff(effective, expiry) + 1)

    if is_own and active:
        booking_status = "BOOKED_BY_US"
    elif active and booking_open <= as_of_month:
        booking_status = "BOOK_NOW"
    elif active:
        booking_status = "WAIT"
    else:
        booking_status = "NOT_ACTIVE"

    return {
        "item_code": row["item_code"],
        "agency_name": row["agency_name"],
        "deduction_amount": row["deduction_amount"],
        "effective_date": effective.isoformat(),
        "expiry_date": expiry.isoformat(),
        "reference_no": row["reference_no"],
        "status": row["status"],
        "is_own_booking": is_own,
        "is_active": active,
        "elapsed_months": elapsed,
        "months_to_expiry": months_to_expiry,
        "scheduled_deduction_months": scheduled_deduction_months,
        "booking_open_date": booking_open.isoformat(),
        "months_until_booking": max(0, _month_diff(as_of_month, booking_open)),
        "booking_status": booking_status,
    }


def analyse_cdas_booking(
    raw_text: str,
    *,
    as_of: date,
    booking_lead_months: int = 6,
    own_item_codes: Iterable[str] = (),
    own_agency_names: Iterable[str] = (),
) -> dict:
    if not raw_text.strip():
        raise ValueError("CDAS text is required.")
    if not 0 <= booking_lead_months <= 60:
        raise ValueError("Booking lead months must be between 0 and 60.")

    own_codes = {str(value).strip() for value in own_item_codes if str(value).strip()}
    own_agencies = {_normalise(value) for value in own_agency_names if value.strip()}
    parsed_rows = parse_cdas_text(raw_text)
    deductions = [
        _serialise_row(
            row,
            as_of=as_of,
            booking_lead_months=booking_lead_months,
            own_item_codes=own_codes,
            own_agencies=own_agencies,
        )
        for row in parsed_rows
    ]

    active_rows = [row for row in deductions if row["is_active"]]
    own_active = [row for row in active_rows if row["is_own_booking"]]
    competitor_active = [row for row in active_rows if not row["is_own_booking"]]

    own_active.sort(key=lambda row: (row["expiry_date"], row["agency_name"]))
    competitor_active.sort(key=lambda row: (row["booking_open_date"], row["expiry_date"]))

    opportunity = competitor_active[0] if competitor_active else None
    next_possible_booking_date: str | None = None

    if own_active:
        decision = "ALREADY_BOOKED"
        primary = own_active[0]
        decision_message = (
            f"Already booked by us with {primary['agency_name']} for "
            f"{primary['elapsed_months']} month(s) since the effective month. "
            f"The deduction expires {primary['expiry_date'][:7]}."
        )
    elif opportunity and opportunity["booking_status"] == "BOOK_NOW":
        decision = "BOOK_NOW"
        next_possible_booking_date = opportunity["booking_open_date"]
        decision_message = (
            f"Booking window is open now. {opportunity['agency_name']} expires "
            f"{opportunity['expiry_date'][:7]} and entered the {booking_lead_months}-month "
            "booking window already."
        )
    elif opportunity:
        decision = "WAIT_UNTIL"
        next_possible_booking_date = opportunity["booking_open_date"]
        decision_message = (
            f"Next possible booking month is {opportunity['booking_open_date'][:7]}, based on "
            f"{opportunity['agency_name']} expiring {opportunity['expiry_date'][:7]} and a "
            f"{booking_lead_months}-month booking window."
        )
    else:
        decision = "BOOK_NOW"
        next_possible_booking_date = date(as_of.year, as_of.month, 1).isoformat()
        decision_message = "No active deduction was found. The client can be considered for booking now."

    return {
        "as_of": as_of.isoformat(),
        "booking_lead_months": booking_lead_months,
        "decision": decision,
        "decision_message": decision_message,
        "next_possible_booking_date": next_possible_booking_date,
        "total_monthly_deductions": round(sum(row["deduction_amount"] for row in active_rows), 2),
        "own_monthly_deductions": round(sum(row["deduction_amount"] for row in own_active), 2),
        "competitor_monthly_deductions": round(
            sum(row["deduction_amount"] for row in competitor_active), 2
        ),
        "own_bookings": own_active,
        "opportunity": opportunity,
        "deductions": deductions,
    }
