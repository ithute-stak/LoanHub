"""Per-company operator authorization for a shared, approved Wacom workstation."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from database.base import Base


class WacomWorkstationOperator(Base):
    __tablename__ = "wacom_workstation_operators"
    __table_args__ = (
        UniqueConstraint("company_id", "workstation_id", "employee_user_id", name="uq_wacom_pc_company_device_employee"),
        CheckConstraint("status IN ('active','revoked')", name="ck_wacom_pc_operator_status"),
        Index("ix_wacom_pc_operator_employee", "company_id", "employee_user_id", "status"),
    )
    company_id = Column(UUID(as_uuid=True), ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False)
    workstation_id = Column(UUID(as_uuid=True), nullable=False)
    employee_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("company_branches.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(16), nullable=False, default="active")
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False)
    revoked_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
