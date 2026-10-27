"""Read-only preflight for component-level allocation evidence.

Installment allocations alone do not specify whether a payment discharged
principal, interest, or fees. Financial rollover posting must refuse invented
component allocations until source evidence can establish the split.
"""
from __future__ import annotations

from decimal import Decimal
from fastapi import HTTPException


def verify_component_allocation_evidence(*, installment, evidence: dict | None) -> dict:
    original = {
        name: Decimal(str(getattr(installment, f"{name}_due") or 0))
        for name in ("principal", "interest", "fee")
    }
    total = Decimal(str(installment.total_due))
    paid = Decimal(str(installment.paid_amount))
    if total != sum(original.values()) or paid < 0 or paid >= total:
        raise HTTPException(status_code=409, detail="Installment totals require reconciliation")
    if not isinstance(evidence, dict):
        raise HTTPException(status_code=409, detail="Signed component allocation evidence is required")
    if not evidence.get("source_reference") or not evidence.get("verified_by"):
        raise HTTPException(status_code=422, detail="Component allocation requires a source reference and verifier")
    applied = {
        name: Decimal(str(evidence.get(f"{name}_paid", -1)))
        for name in original
    }
    if any(v < 0 or v > original[k] for k, v in applied.items()) or sum(applied.values()) != paid:
        raise HTTPException(status_code=409, detail="Component payment split does not reconcile to installment payments")
    remainder = {k: original[k] - applied[k] for k in original}
    if sum(remainder.values()) != total - paid:
        raise HTTPException(status_code=409, detail="Remaining component balances do not reconcile")
    return {
        "remaining_principal": str(remainder["principal"]),
        "remaining_interest": str(remainder["interest"]),
        "remaining_fees": str(remainder["fee"]),
        "evidence_reference": evidence["source_reference"],
        "verified_by": evidence["verified_by"],
    }
