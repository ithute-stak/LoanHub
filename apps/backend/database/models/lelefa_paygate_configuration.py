from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, Integer, String, Text, UniqueConstraint

from database.base import Base


class LelefaPayGateConfiguration(Base):
    """Singleton platform configuration for the LoanHub LelefaPayGate boundary."""

    __tablename__ = "lelefapaygate_configurations"
    __table_args__ = (
        UniqueConstraint("scope", name="uq_lelefapaygate_configurations_scope"),
    )

    scope = Column(String(32), nullable=False, index=True, default="platform")
    enabled = Column(Boolean, nullable=False, default=False)
    base_url = Column(String(500), nullable=False)

    encrypted_api_key = Column(Text, nullable=True)
    api_key_nonce = Column(String(80), nullable=True)
    api_key_encryption_version = Column(String(30), nullable=True)

    encrypted_webhook_secret = Column(Text, nullable=True)
    webhook_secret_nonce = Column(String(80), nullable=True)
    webhook_secret_encryption_version = Column(String(30), nullable=True)

    request_signing_enabled = Column(Boolean, nullable=False, default=True)
    timeout_seconds = Column(Float, nullable=False, default=15.0)
    webhook_tolerance_seconds = Column(Integer, nullable=False, default=300)
    collection_provider = Column(String(50), nullable=False, default="mpesa")
    payout_provider = Column(String(50), nullable=False, default="mpesa")
