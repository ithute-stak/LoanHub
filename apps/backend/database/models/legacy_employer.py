from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class LegacyEmployer(Base):
    __tablename__ = "legacy_employers"
    __table_args__ = (UniqueConstraint("company_id", "normalized_name", name="uq_legacy_employers_company_normalized"),)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    normalized_name = Column(String(120), nullable=False)
