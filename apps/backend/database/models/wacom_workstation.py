"""Tenant-scoped Wacom workstation enrollment and one-time challenges.

Enrollment requires a separate approval workflow; records cannot be
self-created by a browser or presented as trusted just because they exist.
"""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class WacomWorkstationEnrollment(Base):
    __tablename__ = "wacom_workstation_enrollments"
    __table_args__ = (
        UniqueConstraint("company_id", "workstation_id", name="uq_wacom_enrollment_company_workstation"),
        CheckConstraint("status IN ('pending','active','revoked')", name="ck_wacom_enrollment_status"),
        CheckConstraint("octet_length(ed25519_public_key) = 32", name="ck_wacom_enrollment_public_key_bytes"),
        Index("ix_wacom_enrollment_tenant_status", "company_id", "status"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    workstation_id = Column(UUID(as_uuid=True), nullable=False)
    operator_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    ed25519_public_key = Column(LargeBinary, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    approved_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))


class WacomWorkstationChallengeRecord(Base):
    __tablename__ = "wacom_workstation_challenges"
    __table_args__ = (
        UniqueConstraint("nonce", name="uq_wacom_challenge_nonce"),
        CheckConstraint("octet_length(nonce) = 32", name="ck_wacom_challenge_nonce_bytes"),
        Index("ix_wacom_challenge_session", "company_id", "session_id"),
    )

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("wacom_workstation_enrollments.id", ondelete="RESTRICT"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("contract_pad_signing_sessions.id", ondelete="RESTRICT"), nullable=False)
    nonce = Column(LargeBinary, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
