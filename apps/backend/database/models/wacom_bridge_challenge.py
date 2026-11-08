"""One-use, operator-specific device proof challenges for shared Wacom PCs."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomBridgeChallenge(Base):
    __tablename__ = "wacom_bridge_challenges"
    __table_args__ = (
        UniqueConstraint("nonce", name="uq_wacom_bridge_challenge_nonce"),
        Index("ix_wacom_bridge_challenge_operator", "company_id", "employee_user_id", "workstation_id"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    employee_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    workstation_id = Column(UUID(as_uuid=True), nullable=False)
    nonce = Column(LargeBinary(32), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
