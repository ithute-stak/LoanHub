"""Short-lived server-side Wacom bridge sessions; only SHA-256 bearer digests stored."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomBridgeSession(Base):
    __tablename__ = "wacom_bridge_sessions"
    __table_args__ = (
        Index("ix_wacom_bridge_session_actor", "company_id", "employee_user_id", "workstation_id"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    employee_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    workstation_id = Column(UUID(as_uuid=True), nullable=False)
    token_sha256 = Column(LargeBinary(32), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
