"""Exact-loan legacy quarantine predicates.

Historical capture provenance is keyed by loan UUID and tenant, never by
borrower identity. This module deliberately does not alter balances or status.
A later administrator-controlled lock can use these predicates to exclude
legacy loans from operational queries and block their mutations.
"""
from sqlalchemy import and_, exists, select

from database.models.legacy_loan_capture import LegacyLoanCapture


def legacy_capture_exists_for_loan(loan_model):
    """Correlated SQL expression for a loan's own legacy capture only."""
    return exists(
        select(LegacyLoanCapture.loan_id).where(
            and_(
                LegacyLoanCapture.loan_id == loan_model.id,
                LegacyLoanCapture.company_id == loan_model.company_id,
            )
        )
    )


def exclude_legacy_captured_loans(query, loan_model):
    """Exclude proven legacy-captured loans; leave unlinked loans unchanged."""
    return query.filter(~legacy_capture_exists_for_loan(loan_model))
