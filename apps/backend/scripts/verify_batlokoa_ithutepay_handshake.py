"""Run the signed, read-only Batlokoa ↔ IthutePay handshake from LoanHub.

Disabled by default. No request is sent unless the feature flag and dedicated
runtime secret have been configured. Does not create financial transactions.
"""
from __future__ import annotations

import json

from sqlalchemy import func, select

from database.models.company import LoanCompany
from database.session import SessionLocal
from integrations.ithutepay_batlokoa_handshake import (
    COMPANY_ID, BatlokoaHandshakeError, perform_readonly_handshake,
)


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(LoanCompany)) != 1:
            raise BatlokoaHandshakeError("Expected exactly one LoanHub company")
        company = db.scalar(select(LoanCompany).limit(1))
        if not company or str(company.id) != COMPANY_ID or not company.is_active:
            raise BatlokoaHandshakeError("LoanHub company binding is not verified")
    result = perform_readonly_handshake(company_id=COMPANY_ID)
    print(json.dumps(result, indent=2))
    print("No payments, payouts or fee postings initiated.")


if __name__ == "__main__":
    main()
