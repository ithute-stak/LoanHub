from __future__ import annotations

import re


_PROFILE_LABELS = (
    "Employee No",
    "Name",
    "Surname",
    "Gender",
    "Date of Birth",
    "NID",
    "Employer",
    "Joining Date",
    "End Date",
    "Early Retirement Date",
    "Compulsory Retirement Date",
)

_STOP_LABELS = {
    *[label.lower() for label in _PROFILE_LABELS],
    "max available deduction amount",
    "new consolidation application",
    "max available after deleting the selected deductions",
    "description",
    "new deduction application",
    "agency",
}


def _clean(raw_text: str) -> str:
    return raw_text.replace("\u00a0", " ").replace("**", "")


def _normalise_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _looks_like_label_or_section(line: str) -> bool:
    compact = _normalise_line(line).strip(":").lower()
    for label in _STOP_LABELS:
        if compact == label or compact.startswith(f"{label}: ") or compact.startswith(f"{label} "):
            return True
    if compact.startswith("agency *"):
        return True
    if line.lstrip().startswith("|"):
        return True
    return False


def _strip_search_noise(value: str) -> str:
    cleaned = _normalise_line(value)
    cleaned = re.sub(r"(?i)^search\s*", "", cleaned).strip()
    cleaned = re.sub(r"(?i)\s*search$", "", cleaned).strip()
    return cleaned


def _extract_value(cleaned_text: str, label: str) -> str | None:
    lines = cleaned_text.splitlines()
    pattern = re.compile(rf"^\s*{re.escape(label)}\s*:?[ \t]*(.*)$", re.IGNORECASE)

    for index, raw_line in enumerate(lines):
        match = pattern.match(raw_line)
        if not match:
            continue

        inline = _strip_search_noise(match.group(1))
        if inline:
            return inline

        for candidate_raw in lines[index + 1 :]:
            candidate = _normalise_line(candidate_raw)
            if not candidate:
                continue
            if _looks_like_label_or_section(candidate):
                return None
            candidate = _strip_search_noise(candidate)
            return candidate or None
        return None

    return None


def _extract_agency(cleaned_text: str) -> tuple[str | None, str | None]:
    compact = re.sub(r"[ \t\r\n]+", " ", cleaned_text)
    match = re.search(
        r"(?i)Agency\s*\*\s*(?:Search\s*)?(\d{3,8})\s*\(([^)]+)\)",
        compact,
    )
    if not match:
        return None, None
    return match.group(1).strip(), _normalise_line(match.group(2))


def parse_cdas_autofill_context(raw_text: str) -> dict:
    """Extract the CDAS fields used to auto-fill the booking-rules form.

    CDAS often copies form controls with labels and values on different lines.
    The older screen parser only handled same-line values, which caused valid
    employee details to be returned as null. This parser deliberately accepts
    both same-line and next-line clipboard layouts while stopping at the next
    recognised label/table section so one field cannot consume another label.
    """
    cleaned = _clean(raw_text)

    profile = {label: _extract_value(cleaned, label) for label in _PROFILE_LABELS}
    name = profile["Name"]
    surname = profile["Surname"]
    full_name = " ".join(part for part in (name, surname) if part).strip() or None

    agency_code, agency_name = _extract_agency(cleaned)

    return {
        "profile": {
            "employee_no": profile["Employee No"],
            "name": name,
            "surname": surname,
            "full_name": full_name,
            "gender": profile["Gender"],
            "nid": profile["NID"],
            "employer": profile["Employer"],
        },
        "application_context": {
            "new_deduction_agency_code": agency_code,
            "new_deduction_agency_name": agency_name,
        },
    }
