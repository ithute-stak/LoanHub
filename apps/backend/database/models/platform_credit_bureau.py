from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class PlatformCreditBureauConfiguration(Base):
    """Platform-owner controlled provider configuration for shared credit bureaus.

    Provider credentials and the product-specific API contract are intentionally
    platform scoped. Lending companies only opt in to use the provider; they do
    not receive or manage the platform's Experian secrets.
    """

    __tablename__ = "platform_credit_bureau_configurations"
    __table_args__ = (
        UniqueConstraint("provider", name="uq_platform_credit_bureau_provider"),
    )

    provider = Column(String(40), nullable=False, index=True)
    environment = Column(String(30), nullable=False, default="sandbox")
    is_enabled = Column(Boolean, nullable=False, default=False)
    configuration = Column(JSONB, nullable=False, default=dict)
    encrypted_credentials = Column(Text, nullable=True)
    last_test_status = Column(String(100), nullable=True)
    last_tested_at = Column(DateTime, nullable=True)
    configured_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    configured_by = relationship("User", foreign_keys=[configured_by_user_id])
