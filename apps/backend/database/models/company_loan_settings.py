from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class CompanyLoanSettings(Base):
    """Company-wide lending preferences that are not tied to one loan product."""

    __tablename__ = "company_loan_settings"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_loan_settings_company_id"),
    )

    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    default_contract_template_style = Column(
        String(50),
        nullable=False,
        default="loanhub_standard",
        server_default="loanhub_standard",
    )

    company = relationship("LoanCompany")
