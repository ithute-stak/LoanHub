# database/models/notification.py

from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from database.base import Base


class Broadcast(Base):
    __tablename__ = "broadcast"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    channel = Column(String(120), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    event_type = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=True)
    entity_id = Column(String(100), nullable=True)

    data = Column(JSONB, default=dict)
    is_read = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="broadcast")