from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import NotificationType


class Notification(Base):
    __tablename__ = "notifications"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
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

    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(
        Enum(NotificationType),
        nullable=False,
        default=NotificationType.SYSTEM,
        index=True,
    )

    event_type = Column(String(150), nullable=False, default="system.event", index=True)
    action = Column(String(40), nullable=False, default="view")
    entity_type = Column(String(120), nullable=True, index=True)
    entity_id = Column(String(120), nullable=True, index=True)
    action_url = Column(String(500), nullable=True)
    icon = Column(String(80), nullable=True)
    priority = Column(String(30), nullable=False, default="normal", index=True)
    data = Column(JSONB, nullable=False, default=dict)
    deduplication_key = Column(String(255), nullable=True, index=True)

    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False, index=True)
    archived_at = Column(DateTime, nullable=True)

    # Retained for compatibility with existing installations.
    related_loan_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_offer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_offers.id", ondelete="SET NULL"),
        nullable=True,
    )

    recipient = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="notifications",
    )
    actor = relationship("User", foreign_keys=[actor_user_id])
    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
