from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CdasLoanDeduction(Base):
    """Durable link between a LoanHub facility/application and one CDAS deduction.

    LoanHub loan status and CDAS deduction status intentionally remain separate.
    The environment is snapshotted so a test deduction can never silently become
    a live deduction when a company later changes its CDAS configuration.
    """

    __tablename__ = "cdas_loan_deductions"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_cdas_deduction_application"),
        UniqueConstraint("loan_id", name="uq_cdas_deduction_loan"),
        UniqueConstraint(
            "company_id",
            "environment",
            "reference_no",
            name="uq_cdas_deduction_company_environment_reference",
        ),
        UniqueConstraint(
            "company_id",
            "environment",
            "deduction_id",
            name="uq_cdas_deduction_company_environment_provider_id",
        ),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("direct_loan_applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_company_loan.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    environment = Column(String(20), nullable=False, index=True)
    employee_no = Column(String(100), nullable=False, index=True)
    deduction_id = Column(Integer, nullable=True, index=True)
    item_code = Column(String(100), nullable=False)
    reference_no = Column(String(200), nullable=False, index=True)
    loan_policy = Column(Integer, nullable=False, default=0)
    deduction_amount = Column(Numeric(15, 2), nullable=False)
    principal_amount = Column(Numeric(15, 2), nullable=False)
    total_installment = Column(Integer, nullable=False, default=0)
    effective_month = Column(String(32), nullable=False)

    cdas_status = Column(Integer, nullable=True, index=True)
    lifecycle_status = Column(String(50), nullable=False, default="registration_pending", index=True)
    last_request_type = Column(Integer, nullable=True)
    requires_reconciliation = Column(Boolean, nullable=False, default=False, index=True)
    last_provider_response = Column(JSONB, nullable=False, default=dict)
    last_error = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    registered_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    company = relationship("LoanCompany")
    borrower = relationship("Borrower")
    application = relationship("DirectLoanApplication", foreign_keys=[application_id])
    loan = relationship("ClientCompanyLoan", foreign_keys=[loan_id])
    events = relationship(
        "CdasDeductionEvent",
        back_populates="deduction",
        cascade="all, delete-orphan",
        order_by="CdasDeductionEvent.occurred_at",
    )


class CdasDeductionEvent(Base):
    """Append-only operational history for provider-facing CDAS mutations."""

    __tablename__ = "cdas_deduction_events"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deduction_link_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cdas_loan_deductions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type = Column(String(60), nullable=False, index=True)
    request_type = Column(Integer, nullable=True)
    request_snapshot = Column(JSONB, nullable=False, default=dict)
    response_snapshot = Column(JSONB, nullable=False, default=dict)
    provider_status_code = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=True, index=True)
    message = Column(Text, nullable=True)
    occurred_at = Column(DateTime, nullable=False)

    company = relationship("LoanCompany")
    deduction = relationship("CdasLoanDeduction", back_populates="events")
    actor = relationship("User", foreign_keys=[actor_user_id])
