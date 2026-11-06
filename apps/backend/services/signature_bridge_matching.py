"""Signature Bridge remote-side matching rules, packaged with LoanHub backend image.

This pure module NEVER authorizes document signing. Only the server may supply
authenticated operator identity and tenant scope to the caller.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class SignatureCandidate:
    signature_id: str
    signer_id: str
    company_id: str
    status: str = "active"

def normalized_phone_aliases(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise ValueError("Phone field must be a string")
    parts = text.split("/")
    if not 1 <= len(parts) <= 8 or any(not x.strip() for x in parts):
        raise ValueError("Expected 1 to 8 nonempty slash-separated numbers")
    values = []
    for part in parts:
        number = re.sub(r"[\s()\-]", "", part)
        if number.startswith("00266"):
            number = number[5:]
        elif number.startswith("+266"):
            number = number[4:]
        elif number.startswith("266") and len(number) == 11:
            number = number[3:]
        if not re.fullmatch(r"[0-9]{8}", number):
            raise ValueError("Expected an eight-digit Lesotho phone number")
        value = "266" + number
        if value not in values:
            values.append(value)
    return tuple(values)

def resolve_candidates(*, company_id: str, candidates: Iterable[SignatureCandidate]) -> dict:
    if not company_id:
        raise ValueError("Company scope is required")
    selected = {
        item.signature_id: item for item in candidates
        if item.company_id == company_id and item.status == "active"
    }
    signer_ids = {item.signer_id for item in selected.values()}
    if not selected:
        status = "not_found"
    elif len(selected) != 1 or len(signer_ids) != 1:
        status = "conflict"
    else:
        status = "match"
    return {
        "status": status,
        "match_count": len(selected),
        "signature_ids": sorted(selected) if status == "match" else [],
        "auto_apply": False,
        "requires_document_consent": True,
    }
