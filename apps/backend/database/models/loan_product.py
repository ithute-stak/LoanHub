# database/models/loan_product.py
from sqlalchemy import Column, String, Text, Numeric, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class LoanProduct(Base):
    __tablename__ = "loan_products"

    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    min_amount = Column(Numeric(12, 2), nullable=False)
    max_amount = Column(Numeric(12, 2), nullable=False)

    min_term_months = Column(Integer, nullable=False)
    max_term_months = Column(Integer, nullable=False)

    interest_method = Column(String(50), nullable=False, default="micro_loan", index=True)
    interest_rate_percent = Column(Numeric(6, 3), nullable=False, default=0)
    processing_fee = Column(Numeric(12, 2), nullable=False, default=0)

    is_active = Column(Boolean, nullable=False, default=True)

    company = relationship("LoanCompany", back_populates="loan_products")