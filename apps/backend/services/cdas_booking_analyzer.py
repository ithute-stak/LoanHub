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


def _clean_screen_text(raw_text: str) -> str:
    return raw_text.replace("\u00a0", " ").replace("**", "")


def _parse_month(value: str) -> date:
    match = re.fullmatch(r"(\d{4})-([A-Za-z]{3})", value.strip())
    if not match:
        raise ValueError(f"Unsupported CDAS month: {value}")
    month = _MONTHS.get(match.group(2).lower())
    if not month:
        raise ValueError(f"Unsupported CDAS month: {value}")
    return date(int(match.group(1)), month, 1)


def _parse_ui_date(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    for pattern in (
        r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})",
        r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})",
    ):
        match = re.fullmatch(pattern, cleaned)
        if not match:
            continue
        try:
            return date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            ).isoformat()
        except ValueError:
            return None
    return None


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


def _parse_signed_amount(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(
        r"(?P<sign>-)?\s*(?:M|LSL)?\s*(?P<amount>[\d][\d,\s]*(?:\.\d{1,2})?)",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    amount = float(match.group("amount").replace(",", "").replace(" ", ""))
    return -amount if match.group("sign") else amount


def _extract_screen_value(cleaned_text: str, label: str) -> str | None:
    match = re.search(
        rf"(?im)^[ \t]*{re.escape(label)}[ \t]*:?[ \t]*(.*)$",
        cleaned_text,
    )
    if not match:
        return None
    value = match.group(1).strip()
    if not value:
        return None
    if label.lower() == "employee no" and value.lower() == "search":
        return None
    return value


def parse_cdas_screen_context(raw_text: str, *, as_of: date | None = None) -> dict:
    """Extract useful non-deduction fields from a copied CDAS screen."""
    cleaned = _clean_screen_text(raw_text)

    employee_no = _extract_screen_value(cleaned, "Employee No")
    name = _extract_screen_value(cleaned, "Name")
    surname = _extract_screen_value(cleaned, "Surname")
    full_name = " ".join(part for part in (name, surname) if part).strip() or None

    profile = {
        "employee_no": employee_no,
        "name": name,
        "surname": surname,
        "full_name": full_name,
        "gender": _extract_screen_value(cleaned, "Gender"),
        "date_of_birth": _parse_ui_date(_extract_screen_value(cleaned, "Date of Birth")),
        "nid": _extract_screen_value(cleaned, "NID"),
        "employer": _extract_screen_value(cleaned, "Employer"),
        "joining_date": _parse_ui_date(_extract_screen_value(cleaned, "Joining Date")),
        "end_date": _parse_ui_date(_extract_screen_value(cleaned, "End Date")),
        "early_retirement_date": _parse_ui_date(
            _extract_screen_value(cleaned, "Early Retirement Date")
        ),
        "compulsory_retirement_date": _parse_ui_date(
            _extract_screen_value(cleaned, "Compulsory Retirement Date")
        ),
    }

    max_available = _parse_signed_amount(
        _extract_screen_value(cleaned, "Max Available Deduction Amount")
    )
    after_selected_match = re.search(
        r"(?im)^[ \t]*Max available after deleting the selected deductions"
        r"[ \t]*:[ \t]*(.*)$",
        cleaned,
    )
    after_selected = _parse_signed_amount(
        after_selected_match.group(1).strip() if after_selected_match else None
    )

    basis = after_selected if after_selected is not None else max_available
    if basis is None:
        capacity_status = "UNKNOWN"
        shortfall_amount = 0.0
    elif basis < 0:
        capacity_status = "NEGATIVE_AVAILABLE"
        shortfall_amount = round(abs(basis), 2)
    elif basis == 0:
        capacity_status = "NO_HEADROOM"
        shortfall_amount = 0.0
    else:
        capacity_status = "AVAILABLE"
        shortfall_amount = 0.0

    agency_match = re.search(
        r"(?im)^[ \t]*Agency[ \t]*\*.*?(\d{3,8}).*?\(([^)\n]+)\)[ \t]*$",
        cleaned,
    )
    application_context = {
        "new_deduction_agency_code": agency_match.group(1) if agency_match else None,
        "new_deduction_agency_name": agency_match.group(2).strip() if agency_match else None,
    }

    retirement_analysis = {
        "early_retirement_date": profile["early_retirement_date"],
        "compulsory_retirement_date": profile["compulsory_retirement_date"],
        "days_until_early_retirement": None,
        "days_until_compulsory_retirement": None,
    }
    if as_of:
        if profile["early_retirement_date"]:
            retirement_analysis["days_until_early_retirement"] = (
                date.fromisoformat(profile["early_retirement_date"]) - as_of
            ).days
        if profile["compulsory_retirement_date"]:
            retirement_analysis["days_until_compulsory_retirement"] = (
                date.fromisoformat(profile["compulsory_retirement_date"]) - as_of
            ).days

    return {
        "profile": profile,
        "capacity": {
            "max_available_deduction_amount": max_available,
            "max_available_after_selected_deductions": after_selected,
            "status": capacity_status,
            "shortfall_amount": shortfall_amount,
        },
        "retirement_analysis": retirement_analysis,
        "application_context": application_context,
    }


def _parse_pipe_row(line: str) -> dict | None:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if not cells or all(not cell or re.fullmatch(r"-+", cell) for cell in cells):
        return None

    status_index = next(
        (
            index
            for index in range(len(cells) - 1, -1, -1)
            if cells[index].lower() in _KNOWN_STATUSES
        ),
        None,
    )
    if status_index is None:
        return None

    item_index = next(
        (
            index
            for index, cell in enumerate(cells[:status_index])
            if re.fullmatch(r"\d{3,8}", cell)
        ),
        None,
    )
    if item_index is None:
        return None

    amount_index = next(
        (
            index
            for index in range(item_index + 1, status_index)
            if re.search(r"(?:M|LSL)\s*[\d,]+", cells[index], re.IGNORECASE)
        ),
        None,
    )
    if amount_index is None:
        return None

    effective_index = next(
        (
            index
            for index in range(amount_index + 1, status_index)
            if re.fullmatch(r"\d{4}-[A-Za-z]{3}", cells[index])
        ),
        None,
    )
    if effective_index is None:
        return None

    expiry: date | None = None
    reference_start = effective_index + 1
    if reference_start < status_index:
        candidate = cells[reference_start]
        if re.fullmatch(r"\d{4}-[A-Za-z]{3}", candidate):
            expiry = _parse_month(candidate)
            reference_start += 1
        elif not candidate:
            reference_start += 1

    agency_cells = [cell for cell in cells[item_index + 1 : amount_index] if cell]
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
        "expiry_date": expiry,
        "reference_no": " ".join(
            cell for cell in cells[reference_start:status_index] if cell
        ).strip(),
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
        expiry = parsed.get("expiry_date")
        key = (
            parsed["item_code"],
            parsed["reference_no"],
            expiry.isoformat() if expiry else "",
        )
        if key not in seen:
            seen.add(key)
            rows.append(parsed)

    if not rows:
        raise ValueError(
            "No CDAS deduction rows were recognised. Paste the deduction rows with item code, "
            "agency, amount, effective month, reference and status. Expiry may be blank; "
            "LoanHub will flag it for review."
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
    expiry = row.get("expiry_date")
    as_of_month = date(as_of.year, as_of.month, 1)
    reported_active = row["status"].lower() == "active"
    is_own = _is_own_booking(row, own_item_codes, own_agencies)

    missing_expiry = expiry is None
    date_conflict = bool(expiry and expiry < effective)
    excluded_from_booking = missing_expiry or date_conflict

    if missing_expiry:
        data_quality_status = "MISSING_EXPIRY"
        data_quality_message = (
            "CDAS reports this deduction as Active but does not provide an expiry month. "
            "The amount is retained in reported financial totals, but this row is excluded "
            "from booking-window calculations until the expiry is known."
        )
    elif date_conflict:
        data_quality_status = "DATE_CONFLICT"
        data_quality_message = (
            f"Effective month {effective:%Y-%m} is later than expiry month {expiry:%Y-%m}. "
            "This CDAS row is excluded from booking calculations until it is corrected."
        )
    else:
        data_quality_status = "OK"
        data_quality_message = None

    active = reported_active and not excluded_from_booking
    booking_open = (
        _shift_month(expiry, -booking_lead_months)
        if expiry and not excluded_from_booking
        else None
    )
    elapsed = max(0, _month_diff(effective, as_of_month)) if not excluded_from_booking else None
    months_to_expiry = (
        max(0, _month_diff(as_of_month, expiry))
        if expiry and not excluded_from_booking
        else None
    )
    scheduled_deduction_months = (
        max(1, _month_diff(effective, expiry) + 1)
        if expiry and not excluded_from_booking
        else None
    )

    if missing_expiry:
        booking_status = "DATA_INCOMPLETE"
    elif date_conflict:
        booking_status = "DATA_CONFLICT"
    elif is_own and active:
        booking_status = "BOOKED_BY_US"
    elif active and booking_open and booking_open <= as_of_month:
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
        "expiry_date": expiry.isoformat() if expiry else None,
        "reference_no": row["reference_no"],
        "status": row["status"],
        "reported_active": reported_active,
        "is_own_booking": is_own,
        "is_active": active,
        "excluded_from_booking": excluded_from_booking,
        "data_quality_status": data_quality_status,
        "data_quality_message": data_quality_message,
        "elapsed_months": elapsed,
        "months_to_expiry": months_to_expiry,
        "scheduled_deduction_months": scheduled_deduction_months,
        "booking_open_date": booking_open.isoformat() if booking_open else None,
        "months_until_booking": (
            max(0, _month_diff(as_of_month, booking_open)) if booking_open else None
        ),
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
    screen_context = parse_cdas_screen_context(raw_text, as_of=as_of)
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

    data_quality_issues = [row for row in deductions if row["excluded_from_booking"]]
    active_rows = [row for row in deductions if row["is_active"]]
    reported_active_rows = [row for row in deductions if row["reported_active"]]
    own_active = [row for row in active_rows if row["is_own_booking"]]
    competitor_active = [row for row in active_rows if not row["is_own_booking"]]

    own_active.sort(key=lambda row: (row["expiry_date"] or "", row["agency_name"]))
    competitor_active.sort(
        key=lambda row: (row["booking_open_date"] or "", row["expiry_date"] or "")
    )

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
    elif any(row["reported_active"] for row in data_quality_issues):
        decision = "REVIEW_REQUIRED"
        decision_message = (
            "CDAS contains Active deduction data that cannot be used safely for booking timing. "
            "LoanHub has retained the amounts for financial analysis but will not calculate a "
            "booking window from a missing or contradictory expiry."
        )
    else:
        decision = "BOOK_NOW"
        next_possible_booking_date = date(as_of.year, as_of.month, 1).isoformat()
        decision_message = "No valid active deduction was found. The client can be considered for booking now."

    reported_active_total = round(sum(row["deduction_amount"] for row in reported_active_rows), 2)
    excluded_total = round(
        sum(
            row["deduction_amount"]
            for row in data_quality_issues
            if row["reported_active"]
        ),
        2,
    )

    return {
        "as_of": as_of.isoformat(),
        "booking_lead_months": booking_lead_months,
        **screen_context,
        "decision": decision,
        "decision_message": decision_message,
        "next_possible_booking_date": next_possible_booking_date,
        "reported_active_monthly_deductions": reported_active_total,
        "total_monthly_deductions": round(sum(row["deduction_amount"] for row in active_rows), 2),
        "own_monthly_deductions": round(sum(row["deduction_amount"] for row in own_active), 2),
        "competitor_monthly_deductions": round(
            sum(row["deduction_amount"] for row in competitor_active), 2
        ),
        "excluded_monthly_deductions": excluded_total,
        "data_quality_issue_count": len(data_quality_issues),
        "data_quality_issues": data_quality_issues,
        "own_bookings": own_active,
        "opportunity": opportunity,
        "deductions": deductions,
    }
