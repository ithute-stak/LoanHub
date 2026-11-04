"""Read-only identification of the only LoanHub lender for IthutePay linking.

This script never creates merchants, changes custody, or calls payment APIs.
Run from /app in the deployed LoanHub backend (database connection required).
"""
from __future__ import annotations

import json

from sqlalchemy import select, func

from database.models.company import LoanCompany
from database.session import SessionLocal


def inspect_single_company(db) -> dict:
    count = db.scalar(select(func.count()).select_from(LoanCompany))
    if count != 1:
        return {
            "ready_for_identity_review": False,
            "company_count": int(count or 0),
            "reason": "Expected exactly one LoanHub company; no automatic selection permitted",
        }
    company = db.scalar(select(LoanCompany).limit(1))
    if company is None:
        raise RuntimeError("Company count and company selection disagree")
    return {
        "ready_for_identity_review": True,
        "company_count": 1,
        "company_id": str(company.id),
        "company_name": company.name,
        "status": str(getattr(company.status, "value", company.status)),
        "active": bool(company.is_active),
        "mode_requested": "ithutepay_master_merchant",
        "platform_fee": "0.00",
        "money_movement_enabled": False,
        "shared_custody_approved": False,
    }


def main() -> None:
    with SessionLocal() as db:
        print(json.dumps(inspect_single_company(db), indent=2))


if __name__ == "__main__":
    main()
