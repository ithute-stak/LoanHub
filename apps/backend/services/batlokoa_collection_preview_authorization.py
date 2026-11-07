"""Fail-closed, read-only Batlokoa loan collection-preview authorization.

No route is exposed, no payment provider is called, and no records are
changed. Trusted LoanHub staff must separately authenticate before invoking
this service. Borrowers cannot use this staff-only authorization boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from core.access_control import COMPANY_MANAGEMENT_ROLES, COLLECTIONS_ROLES, FINANCE_ROLES, TenantContext
from database.models.borrower import Borrower
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus
from integrations.ithutepay_batlokoa_handshake import COMPANY_ID

CENT = Decimal("0.01")
ALLOWED_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}
ALLOWED_ROLES = COLLECTIONS_ROLES | FINANCE_ROLES


class BatlokoaCollectionAuthorizationError(ValueError):
    """Caller, loan, borrower, balance or tenant is not eligible."""


@dataclass(frozen=True)
class AuthorizedCollectionPreview:
    company_id: str
    loan_id: str
    borrower_id: str
    amount: str
    currency: str
    source_reference: str
    payment_execution_enabled: bool = False


def authorize_batlokoa_collection_preview(
    *,
    db,
    context: TenantContext,
    loan_id: UUID,
    borrower_user_id: UUID,
    amount: str | Decimal,
) -> AuthorizedCollectionPreview:
    """Validate existing records, not caller-supplied merchant/shortcode metadata.

    This authorizes a *preview by company staff*, not a borrower debit or
    financial execution. The caller must not convert this into payment
    authority without further approved mandate, idempotency and ledger checks.
    """
    if context.is_platform_admin or context.staff is None or context.user is None:
        raise BatlokoaCollectionAuthorizationError("Active company staff membership required")
    if not context.user.is_active or not context.staff.is_active:
        raise BatlokoaCollectionAuthorizationError("Inactive account or membership")
    if context.role not in ALLOWED_ROLES:
        raise BatlokoaCollectionAuthorizationError("Collection preview role not permitted")
    if context.company_id is None or str(context.company_id) != COMPANY_ID:
        raise BatlokoaCollectionAuthorizationError("Unexpected company boundary")
    if context.staff.company_id != context.company_id:
        raise BatlokoaCollectionAuthorizationError("Company membership mismatch")
    if not isinstance(loan_id, UUID) or not isinstance(borrower_user_id, UUID):
        raise BatlokoaCollectionAuthorizationError("Loan and borrower identity must be UUIDs")

    try:
        requested = Decimal(amount)
    except (InvalidOperation, TypeError, ValueError):
        raise BatlokoaCollectionAuthorizationError("Invalid collection amount") from None
    if (not requested.is_finite() or requested <= 0 or
            requested.as_tuple().exponent < -2 or
            len(requested.as_tuple().digits) > 18):
        raise BatlokoaCollectionAuthorizationError("Collection amount must be positive LSL cents")

    loan = db.get(ClientCompanyLoan, loan_id)
    if loan is None or loan.company_id != context.company_id:
        raise BatlokoaCollectionAuthorizationError("Loan unavailable in company scope")
    if context.role not in COMPANY_MANAGEMENT_ROLES:
        if context.branch_id is None or loan.branch_id != context.branch_id:
            raise BatlokoaCollectionAuthorizationError("Loan outside staff branch scope")
    if loan.status not in ALLOWED_STATUSES or loan.disbursed_at is None:
        raise BatlokoaCollectionAuthorizationError("Loan is not eligible for collection")
    try:
        balance = Decimal(loan.balance)
    except (InvalidOperation, TypeError, ValueError):
        raise BatlokoaCollectionAuthorizationError("Invalid recorded loan balance") from None
    if not balance.is_finite() or balance <= 0 or requested > balance:
        raise BatlokoaCollectionAuthorizationError("Amount exceeds collectible loan balance")

    borrower = db.get(Borrower, loan.borrower_id)
    if borrower is None or borrower.id != loan.borrower_id or borrower.user_id != borrower_user_id:
        raise BatlokoaCollectionAuthorizationError("Borrower is not linked to this loan")

    return AuthorizedCollectionPreview(
        company_id=COMPANY_ID,
        loan_id=str(loan.id),
        borrower_id=str(borrower.id),
        amount=format(requested, ".2f"),
        currency="LSL",
        source_reference=f"loan_{loan.id.hex}",
    )
