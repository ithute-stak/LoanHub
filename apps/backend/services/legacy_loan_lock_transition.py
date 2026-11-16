"""Audited company legacy-lock transitions.

Activation is deliberately fail-closed until the complete write-path audit is
approved. This service is not exposed as a public route.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.company_loan_settings import CompanyLoanSettings


def transition_legacy_loan_lock(
    db: Session,
    *,
    company_id,
    actor_user_id,
    actor_role: str,
    enabled: bool,
) -> bool:
    """Persist an authorized transition with its audit event atomically.

    Caller must enforce company management authorization. Enabling remains
    unavailable until deployment readiness is independently verified.
    """
    if enabled:
        raise HTTPException(
            status_code=409,
            detail="Legacy loan lock activation is not yet available",
        )

    row = (
        db.query(CompanyLoanSettings)
        .filter(CompanyLoanSettings.company_id == company_id)
        .with_for_update()
        .first()
    )
    if row is None:
        return False
    if not row.legacy_loan_lock_enabled:
        return False

    row.legacy_loan_lock_enabled = False
    db.add(
        AuditLog(
            user_id=actor_user_id,
            company_id=company_id,
            action="legacy_loan_lock.disabled",
            table_name="company_loan_settings",
            entity_type="company_loan_settings",
            record_id=row.id,
            description="Legacy loan lock disabled by company management",
            actor_role=actor_role,
            before_data={"legacy_loan_lock_enabled": True},
            after_data={"legacy_loan_lock_enabled": False},
            changed_fields=["legacy_loan_lock_enabled"],
        )
    )
    db.commit()
    return False
