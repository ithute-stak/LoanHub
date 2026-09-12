from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CompanySocialShareSettings(Base):
    __tablename__ = "company_social_share_settings"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_social_share_settings_company"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_sharing_enabled = Column(Boolean, nullable=False, default=False)
    default_expiry_hours = Column(Integer, nullable=False, default=24)
    default_message = Column(Text, nullable=True)
    enabled_channels = Column(
        JSONB,
        nullable=False,
        default=lambda: ["native", "whatsapp", "email"],
    )

    whatsapp_number = Column(String(40), nullable=True)
    facebook_url = Column(String(500), nullable=True)
    instagram_url = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    x_handle = Column(String(100), nullable=True)
    telegram_username = Column(String(100), nullable=True)
    youtube_url = Column(String(500), nullable=True)

    configured_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    company = relationship("LoanCompany")
    configured_by_user = relationship("User", foreign_keys=[configured_by_user_id])


class ExternalFileShare(Base):
    __tablename__ = "external_file_shares"

    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("managed_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    label = Column(String(180), nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, nullable=False, default=0)
    allow_download = Column(Boolean, nullable=False, default=True)

    file = relationship("ManagedFile")
    company = relationship("LoanCompany")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
