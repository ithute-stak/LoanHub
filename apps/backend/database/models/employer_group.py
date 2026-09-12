from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship

from database.base import Base


class EmployerGroup(Base):
    __tablename__ = "employer_groups"

    code = Column(String(40), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    borrowers = relationship(
        "Borrower",
        back_populates="employer_group",
    )
