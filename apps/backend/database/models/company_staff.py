from sqlalchemy import Boolean, Column, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import UserRole


class CompanyStaff(Base):
    __tablename__ = "company_staff"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "company_id",
            "role",
            name="uq_company_staff_user_company_role",
        ),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    role = Column(Enum(UserRole), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    user = relationship("User", back_populates="company_staff")
    company = relationship("LoanCompany", back_populates="staff_members")
    branch = relationship("CompanyBranch", back_populates="staff_members")
    employee_profile = relationship(
        "EmployeeProfile",
        foreign_keys="EmployeeProfile.staff_id",
        back_populates="staff",
        uselist=False,
        cascade="all, delete-orphan",
    )
