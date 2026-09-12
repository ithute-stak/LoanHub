from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UUID,
)
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    email = Column(
        String(150),
        unique=True,
        index=True,
        nullable=True,
    )

    phone = Column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )

    # Immutable subject (`sub`) from the centralized !thute Auth service.
    # This is deliberately not a foreign key because the identity service owns
    # a separate database and product databases must never cross-reference it.
    auth_user_id = Column(
        UUID(as_uuid=True),
        unique=True,
        index=True,
        nullable=True,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    role = Column(
        Enum(UserRole),
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    must_change_password = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    last_seen_at = Column(
        DateTime,
        nullable=True,
        index=True,
    )

    person = relationship(
        "Person",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    broadcast = relationship(
        "Broadcast",
        back_populates="user",
    )

    borrower_profile = relationship(
        "Borrower",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    company_staff = relationship(
        "CompanyStaff",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    notifications = relationship(
        "Notification",
        foreign_keys="Notification.user_id",
        back_populates="recipient",
        cascade="all, delete-orphan",
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    jti = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    revoked = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    expires_at = Column(
        DateTime,
        nullable=False,
    )

    session_version = Column(String(20), nullable=False, default="1")
    device_name = Column(String(160), nullable=True)
    ip_hash = Column(String(64), nullable=True)
    user_agent = Column(String(500), nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship(
        "User",
        back_populates="refresh_tokens",
    )
