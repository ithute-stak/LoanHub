from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class SystemErrorLog(Base):
    __tablename__ = "system_error_logs"

    request_id = Column(String(100), nullable=True, index=True)
    fingerprint = Column(
        String(128),
        nullable=False,
        unique=True,
    )

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

    method = Column(String(20), nullable=True)
    path = Column(String(500), nullable=False, index=True)
    status_code = Column(Integer, nullable=False, default=500, index=True)
    error_type = Column(String(200), nullable=False, index=True)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    severity = Column(String(30), nullable=False, default="error", index=True)
    environment = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    context = Column(JSONB, nullable=False, default=dict)

    occurrence_count = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    is_resolved = Column(Boolean, nullable=False, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes = Column(Text, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])
    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
