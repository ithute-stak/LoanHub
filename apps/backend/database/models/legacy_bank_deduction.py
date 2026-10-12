from sqlalchemy import Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class LegacyBankDeduction(Base):
    """Manually captured legacy bank submission, not a loan or payment posting."""
    __tablename__ = "legacy_bank_deductions"
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id"), nullable=False, index=True)
    work_group_id = Column(UUID(as_uuid=True), ForeignKey("employer_groups.id"), nullable=False)
    client_name = Column(String(120), nullable=False)
    account_number_encrypted = Column(String(500), nullable=False)
    account_last4 = Column(String(4), nullable=False)
    branch_code = Column(String(6), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
