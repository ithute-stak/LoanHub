"""Isolated historical CDAS import staging; never a loan or payment ledger."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database.base import Base


class CdasHistoricalImportBatch(Base):
    __tablename__ = "cdas_historical_import_batches"
    __table_args__ = (
        UniqueConstraint("company_id", "branch_id", "source_sha256", name="uq_cdas_history_batch_source"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    source_sha256 = Column(String(64), nullable=False, index=True)
    source_filename = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, default="staged", index=True)
    row_count = Column(Integer, nullable=False, default=0)
    invalid_count = Column(Integer, nullable=False, default=0)
    duplicate_count = Column(Integer, nullable=False, default=0)
    imported_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class CdasHistoricalImportRow(Base):
    __tablename__ = "cdas_historical_import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "line_number", name="uq_cdas_history_batch_line"),
    )
    batch_id = Column(UUID(as_uuid=True), ForeignKey("cdas_historical_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True, index=True)
    line_number = Column(Integer, nullable=False)
    employee_no = Column(String(100), nullable=False, index=True)
    employee_name = Column(String(255), nullable=True)
    policy_reference = Column(String(200), nullable=False, index=True)
    monthly_amount = Column(Numeric(15, 2), nullable=False)
    principal_amount = Column(Numeric(15, 2), nullable=False)
    total_installments = Column(Integer, nullable=False)
    starting_month = Column(String(40), nullable=True)
    ending_month = Column(String(40), nullable=True)
    reconciliation_status = Column(String(30), nullable=False, default="pending", index=True)
    matched_mandate_id = Column(UUID(as_uuid=True), ForeignKey("cdas_deduction_mandates.id", ondelete="SET NULL"), nullable=True)
    source_record = Column(JSONB, nullable=False, default=dict)
