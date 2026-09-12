from sqlalchemy import Boolean, Column, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CompanyBranch(Base):
    __tablename__ = "company_branches"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "name",
            name="uq_company_branch_name",
        ),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(150), nullable=False)
    district = Column(String(100), nullable=False)
    town = Column(String(100), nullable=True)
    address = Column(Text, nullable=True)

    phone = Column(String(30), nullable=True)
    email = Column(String(150), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_headquarters = Column(Boolean, nullable=False, default=False, index=True)

    company = relationship("LoanCompany", back_populates="branches")
    staff_members = relationship("CompanyStaff", back_populates="branch")
    loans = relationship("ClientCompanyLoan", back_populates="branch")
