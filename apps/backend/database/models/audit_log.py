from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action = Column(String(150), nullable=False, index=True)
    table_name = Column(String(150), nullable=True, index=True)
    entity_type = Column(String(150), nullable=True, index=True)
    record_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    description = Column(Text, nullable=True)
    actor_role = Column(String(80), nullable=True)
    severity = Column(String(30), nullable=False, default="info", index=True)
    status = Column(String(30), nullable=False, default="success", index=True)

    before_data = Column(JSONB, nullable=False, default=dict)
    after_data = Column(JSONB, nullable=False, default=dict)
    changed_fields = Column(JSONB, nullable=False, default=list)
    event_data = Column(JSONB, nullable=False, default=dict)

    request_id = Column(String(100), nullable=True, index=True)
    ip_address = Column(String(100), nullable=True)
    user_agent = Column(String(500), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    previous_hash = Column(String(64), nullable=True, index=True)
    event_hash = Column(String(64), nullable=True, unique=True, index=True)
    hash_version = Column(String(30), nullable=True)
    sealed_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
