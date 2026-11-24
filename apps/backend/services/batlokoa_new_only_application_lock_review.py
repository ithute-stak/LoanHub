"""Offline advisory-lock protocol for proposed new-only loan handoff.

This is NOT an idempotency reservation, an origination writer, a release
authorization, or proof of cross-writer serialization. Other LoanHub
origination writers do not yet use this protocol. No API route calls it.
"""
from __future__ import annotations

import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from services.batlokoa_new_only_application_preflight import (
    NewOnlyApplicationPreflight,
    assess_new_only_application_preflight,
)
from services.batlokoa_new_only_loan_handoff import NewOnlyLoanHandoffDenied
from routers.batlokoa_registration_availability import registration_availability_for_staff

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")


def assess_locked_new_only_application_preflight(
    db: Session,
    *,
    context: TenantContext,
    account_id: UUID,
    product_id: UUID,
    requested_amount: Decimal,
    term_count: int,
    request_key: str,
) -> NewOnlyApplicationPreflight:
    """Non-writing preflight while holding a PostgreSQL transaction lock.

    The tenant owns the transaction, and PostgreSQL releases the lock at
    transaction end. Using a global account lock serializes cooperating
    callers irrespective of company or product; it does NOT serialize
    existing application creation routes that do not acquire this lock.
    Request keys are validated, not stored, and are NOT an idempotency
    guarantee. Every result still forbids creating an application.
    """
    if (
        not isinstance(context, TenantContext)
        or context.is_platform_admin
        or not isinstance(context.company_id, UUID)
        or not isinstance(context.branch_id, UUID)
        or not isinstance(account_id, UUID)
        or not isinstance(product_id, UUID)
        or not isinstance(request_key, str)
        or not _KEY_PATTERN.fullmatch(request_key)
    ):
        raise NewOnlyLoanHandoffDenied("Validated company, branch and request key required")
    # Reject inactive, unapproved, unrelated or branchless employee contexts
    # before attempting to acquire any shared database lock.
    registration_availability_for_staff(context)
    bind = db.get_bind()
    if (
        bind is None
        or bind.dialect.name != "postgresql"
        or db.in_transaction() is not True
    ):
        raise NewOnlyLoanHandoffDenied("Caller-owned PostgreSQL transaction required")

    # No identity values, tokens or request contents are sent to the lock.
    # The whole account, not the request key, is the lock scope.
    lock_key = "loanhub:batlokoa:new-only-application:v1:" + str(account_id)
    acquired = db.execute(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": lock_key},
    ).scalar_one()
    if acquired is not True:
        raise NewOnlyLoanHandoffDenied(
            "A concurrent new-client application review is in progress"
        )

    # The provenance, current staff and product must be rechecked only
    # after lock acquisition, not trusted from an earlier browser preview.
    result = assess_new_only_application_preflight(
        db,
        context=context,
        account_id=account_id,
        product_id=product_id,
        requested_amount=requested_amount,
        term_count=term_count,
    )
    if (
        type(result) is not NewOnlyApplicationPreflight
        or result.can_create_loan_application is not False
        or result.can_disburse_loan is not False
        or result.wrote_financial_records is not False
    ):
        raise NewOnlyLoanHandoffDenied("Loan handoff preflight cannot authorize writes")
    return result
