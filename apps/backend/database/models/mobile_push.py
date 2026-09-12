from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database.base import Base


class MobilePushDevice(Base):
    """One authenticated LoanHub mobile installation registered for push wakeups."""

    __tablename__ = "mobile_push_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_uuid", name="uq_mobile_push_device_user_device"),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_uuid = Column(String(120), nullable=False)
    platform = Column(String(24), nullable=False, default="android")
    provider = Column(String(24), nullable=False, default="fcm")
    push_token = Column(Text, nullable=False)
    app_version = Column(String(40), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    last_seen_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
