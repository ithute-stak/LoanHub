from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.base import Base


class LelefaPayGateWebhookEvent(Base):
    """Durable webhook inbox used for replay-safe financial processing."""

    __tablename__ = "lelefapaygate_webhook_events"

    event_id = Column(String(120), nullable=False, unique=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload_hash = Column(String(64), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    processing_status = Column(String(24), nullable=False, default="received", index=True)
    processing_error = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
