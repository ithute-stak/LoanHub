from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CallManagementPolicy(Base):
    __tablename__ = "call_management_policies"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_call_management_policy_company"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recording_enabled = Column(Boolean, nullable=False, default=False)
    recording_retention_days = Column(Integer, nullable=False, default=30)
    call_metadata_retention_months = Column(Integer, nullable=False, default=24)
    automatic_deletion_enabled = Column(Boolean, nullable=False, default=True)
    live_monitoring_enabled = Column(Boolean, nullable=False, default=False)
    manager_downloads_enabled = Column(Boolean, nullable=False, default=False)
    legal_hold_enabled = Column(Boolean, nullable=False, default=True)
    recording_notice = Column(Text, nullable=True)
    sip_outbound_trunk_id = Column(String(160), nullable=True)
    sip_caller_number = Column(String(40), nullable=True)

    company = relationship("LoanCompany")


class EmployeeCallDevice(Base):
    __tablename__ = "employee_call_devices"
    __table_args__ = (
        UniqueConstraint("company_id", "device_uuid", name="uq_employee_call_device_company_uuid"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    staff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_staff.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_uuid = Column(String(160), nullable=False, index=True)
    device_name = Column(String(180), nullable=True)
    platform = Column(String(40), nullable=False, default="android")
    os_version = Column(String(80), nullable=True)
    app_version = Column(String(80), nullable=True)
    status = Column(String(30), nullable=False, default="active", index=True)
    registered_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True, index=True)
    revoked_at = Column(DateTime, nullable=True)

    staff = relationship("CompanyStaff")
    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")


class ClientCall(Base):
    __tablename__ = "client_calls"
    __table_args__ = (
        UniqueConstraint("company_id", "device_call_uuid", name="uq_client_call_company_device_uuid"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    employee_staff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_staff.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    device_id = Column(
        UUID(as_uuid=True),
        ForeignKey("employee_call_devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    loan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_company_loan.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    device_call_uuid = Column(String(120), nullable=False, index=True)
    phone_number = Column(String(40), nullable=False)
    normalized_phone = Column(String(24), nullable=False, index=True)
    direction = Column(String(20), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="started", index=True)
    started_at = Column(DateTime, nullable=False, index=True)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True, index=True)
    duration_seconds = Column(Integer, nullable=False, default=0)
    recording_status = Column(String(30), nullable=False, default="not_requested", index=True)
    outcome = Column(String(80), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    media_room_name = Column(String(180), nullable=True, unique=True, index=True)

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    employee_staff = relationship("CompanyStaff", foreign_keys=[employee_staff_id])
    device = relationship("EmployeeCallDevice")
    borrower = relationship("Borrower")
    loan = relationship("ClientCompanyLoan")
    recording = relationship(
        "CallRecording",
        back_populates="call",
        uselist=False,
        cascade="all, delete-orphan",
    )
    quality_reviews = relationship(
        "CallQualityReview",
        back_populates="call",
        cascade="all, delete-orphan",
    )


class CallRecording(Base):
    __tablename__ = "call_recordings"
    __table_args__ = (
        UniqueConstraint("call_id", name="uq_call_recording_call"),
        UniqueConstraint("managed_file_id", name="uq_call_recording_managed_file"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    managed_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("managed_files.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    mime_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    checksum = Column(String(128), nullable=True)
    status = Column(String(30), nullable=False, default="pending", index=True)
    deletion_at = Column(DateTime, nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True)

    call = relationship("ClientCall", back_populates="recording")
    managed_file = relationship("ManagedFile")
    company = relationship("LoanCompany")
    legal_holds = relationship(
        "RecordingLegalHold",
        back_populates="recording",
        cascade="all, delete-orphan",
    )


class RecordingLegalHold(Base):
    __tablename__ = "recording_legal_holds"

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recording_id = Column(
        UUID(as_uuid=True),
        ForeignKey("call_recordings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    placed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    released_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="active", index=True)
    placed_at = Column(DateTime, nullable=False)
    released_at = Column(DateTime, nullable=True)

    recording = relationship("CallRecording", back_populates="legal_holds")
    placed_by = relationship("User", foreign_keys=[placed_by_user_id])
    released_by = relationship("User", foreign_keys=[released_by_user_id])


class CallQualityReview(Base):
    __tablename__ = "call_quality_reviews"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "call_id",
            "reviewer_user_id",
            name="uq_call_quality_review_reviewer_call",
        ),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    call_id = Column(
        UUID(as_uuid=True),
        ForeignKey("client_calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    score = Column(Integer, nullable=False)
    compliance_status = Column(String(40), nullable=False, default="not_assessed", index=True)
    customer_care_status = Column(String(40), nullable=False, default="not_assessed", index=True)
    notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=False, index=True)

    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    call = relationship("ClientCall", back_populates="quality_reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_user_id])
