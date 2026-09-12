from sqlalchemy import (
    Column,
    Date,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import (
    Gender,
    MaritalStatus,
)


class Person(Base):
    __tablename__ = "people"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    first_name = Column(
        String(100),
        nullable=False,
    )

    middle_name = Column(
        String(100),
        nullable=True,
    )

    last_name = Column(
        String(100),
        nullable=False,
    )

    gender = Column(
        Enum(Gender),
        nullable=True,
    )

    date_of_birth = Column(
        Date,
        nullable=True,
    )

    national_id = Column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )

    passport_number = Column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )

    marital_status = Column(
        Enum(MaritalStatus),
        nullable=True,
    )

    nationality = Column(
        String(100),
        nullable=True,
        default="Mosotho",
    )

    district = Column(
        String(100),
        nullable=True,
    )

    town_or_village = Column(
        String(150),
        nullable=True,
    )

    physical_address = Column(
        Text,
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="person",
    )

    @property
    def full_name(self) -> str:
        names = [
            self.first_name,
            self.middle_name,
            self.last_name,
        ]

        return " ".join(
            name.strip()
            for name in names
            if name and name.strip()
        )