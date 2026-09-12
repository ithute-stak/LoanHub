from __future__ import annotations

from uuid import UUID

from database.models.enums import PaymentPurpose
from database.models.payment import PaymentTransaction


PLATFORM_RECEIPT_PURPOSES = {
    PaymentPurpose.BORROW_REQUEST_FEE,
    PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE,
    PaymentPurpose.PLATFORM_FEE,
    PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT,
    PaymentPurpose.PLATFORM_TRANSACTION_CHARGE,
    PaymentPurpose.SUBSCRIPTION,
    PaymentPurpose.MARKETPLACE_UNLOCK,
}


def configuration_company_id(transaction: PaymentTransaction) -> UUID | None:
    """Return the owner of provider credentials/fund destination for a payment."""
    if transaction.configuration_scope == "platform":
        return None
    if transaction.configuration_scope == "company":
        return transaction.company_id
    if transaction.purpose in PLATFORM_RECEIPT_PURPOSES:
        return None
    return transaction.company_id
