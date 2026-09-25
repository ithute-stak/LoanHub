from __future__ import annotations

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CdasOfficialMandateState(Base):
    """Official-CDAS state attached one-to-one to an existing LoanHub CDAS mandate.

    The core mandate remains the system-of-record link to borrower and loan.
    This extension stores only provider-specific identifiers and lifecycle state.
    """

    __tablename__ = "cdas_official_mandate_states"
    __table_args__ = (
        UniqueConstraint("mandate_id", name="uq_cdas_official_state_mandate"),
        UniqueConstraint(
            "company_id",
            "environment",
            "reference_no",
            name="uq_cdas_official_state_reference",
        ),
        UniqueConstraint(
            "company_id",
            "environment",
            "deduction_id",
            name="uq_cdas_official_state_deduction_id",
        ),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mandate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cdas_deduction_mandates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("direct_loan_applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    environment = Column(String(20), nullable=False, index=True)
    deduction_id = Column(Integer, nullable=True, index=True)
    item_code = Column(String(100), nullable=False)
    reference_no = Column(String(200), nullable=False, index=True)
    loan_policy = Column(Integer, nullable=False, default=0)
    principal_amount = Column(Numeric(15, 2), nullable=False)
    effective_month = Column(String(32), nullable=False)
    cdas_status = Column(Integer, nullable=True, index=True)
    lifecycle_status = Column(String(60), nullable=False, default="registration_pending", index=True)
    last_request_type = Column(Integer, nullable=True)
    requires_reconciliation = Column(Boolean, nullable=False, default=False, index=True)
    last_provider_response = Column(JSONB, nullable=False, default=dict)
    last_error = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    mandate = relationship("CDASDeductionMandate", foreign_keys=[mandate_id])
    application = relationship("DirectLoanApplication", foreign_keys=[application_id])
    events = relationship(
        "CdasOfficialMandateEvent",
        back_populates="state",
        cascade="all, delete-orphan",
        order_by="CdasOfficialMandateEvent.occurred_at",
    )


class CdasOfficialMandateEvent(Base):
    """Append-only audit trail for official CDAS lifecycle calls."""

    __tablename__ = "cdas_official_mandate_events"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cdas_official_mandate_states.id", ondelete="CASCADE"),
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

    state = relationship("CdasOfficialMandateState", back_populates="events")
    actor = relationship("User", foreign_keys=[actor_user_id])


class CdasApiRequestBudget(Base):
    """Atomic per-CDAS-API-account/environment count of outbound HTTP requests."""

    __tablename__ = "cdas_api_request_budgets"
    __table_args__ = (
        UniqueConstraint(
            "account_key",
            "environment",
            "request_date",
            name="uq_cdas_api_budget_account_env_date",
        ),
    )

    # Attribution only. The quota belongs to the CDAS API account, so deleting a
    # LoanHub company must not reset that account's allowance for the current day.
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_key = Column(String(64), nullable=False, index=True)
    environment = Column(String(20), nullable=False, index=True)
    request_date = Column(Date, nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=0)
    last_request_at = Column(DateTime, nullable=True)


class CdasProviderOperation(Base):
    """Durable state machine for every state-changing CDAS provider request.

    The ledger is written before the provider call. Unresolved fingerprints are
    unique so browser retries, double-clicks and concurrent workers cannot submit
    the same mutation twice while its provider state is still uncertain.
    """

    __tablename__ = "cdas_provider_operations"
    __table_args__ = (
        Index(
            "uq_cdas_provider_operation_unresolved_fingerprint",
            "company_id",
            "environment",
            "fingerprint",
            unique=True,
            postgresql_where=text(
                "state IN ('prepared','submitting','acknowledged','unknown_provider_state','requires_reconciliation')"
            ),
        ),
        Index("ix_cdas_provider_operations_company_created", "company_id", "created_at"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    environment = Column(String(20), nullable=False, index=True)
    operation_type = Column(String(80), nullable=False, index=True)
    state = Column(String(40), nullable=False, default="prepared", index=True)
    employee_no = Column(String(100), nullable=True, index=True)
    deduction_id = Column(Integer, nullable=True, index=True)
    reference_no = Column(String(200), nullable=True, index=True)
    fingerprint = Column(String(64), nullable=False, index=True)
    request_snapshot = Column(JSONB, nullable=False, default=dict)
    response_snapshot = Column(JSONB, nullable=False, default=dict)
    provider_status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    reconciled_at = Column(DateTime, nullable=True)
    requires_reconciliation = Column(Boolean, nullable=False, default=False, index=True)

    actor = relationship("User", foreign_keys=[actor_user_id])
