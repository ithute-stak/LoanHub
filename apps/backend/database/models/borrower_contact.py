from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship as orm_relationship

from database.base import Base


class BorrowerContact(Base):
    """A borrower-authorised contact used when the primary number is unavailable."""

    __tablename__ = "borrower_contacts"

    borrower_id = Column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name = Column(String(200), nullable=False)
    relationship = Column(String(80), nullable=False)
    phone = Column(String(32), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_call_permitted = Column(Boolean, nullable=False, default=True)

    borrower = orm_relationship("Borrower", back_populates="contacts")
