"""Durable new-only assisted registration attempt lifecycle.

No existing LoanHub route invokes this model. The database migration must be
reviewed separately before activation.
"""
from __future__ import annotations

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, String,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class NewClientRegistrationAttempt(Base):
    __tablename__ = "new_client_registration_attempts"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "idempotency_key",
            name="uq_new_client_registration_company_idempotency",
        ),
        CheckConstraint(
            "status IN ('reserved','completed','rejected')",
            name="ck_new_client_registration_status",
        ),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    employee_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    idempotency_key = Column(String(128), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="reserved")
    client_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_borrower_accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    account = relationship("CompanyBorrowerAccount", foreign_keys=[client_account_id])
