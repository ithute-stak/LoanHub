"""LoanHub native HRMS foundation

Revision ID: z9n3p5q7r800
Revises: y8m2n4p6q790
Create Date: 2026-08-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "z9n3p5q7r800"
down_revision: Union[str, Sequence[str], None] = "y8m2n4p6q790"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def audit_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    op.create_table(
        "hr_departments",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("manager_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("cost_centre", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manager_employee_id"], ["employee_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["hr_departments.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("company_id", "code", name="uq_hr_department_company_code"),
        *audit_columns(),
    )
    op.create_index("ix_hr_dept_company", "hr_departments", ["company_id"])
    op.create_index("ix_hr_dept_branch", "hr_departments", ["branch_id"])
    op.create_index("ix_hr_dept_active", "hr_departments", ["is_active"])

    op.create_table(
        "hr_positions",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reports_to_position_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("grade", sa.String(length=60), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("minimum_salary", sa.Numeric(15, 2), nullable=True),
        sa.Column("maximum_salary", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), server_default="LSL", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["hr_departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reports_to_position_id"], ["hr_positions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("company_id", "code", name="uq_hr_position_company_code"),
        *audit_columns(),
    )
    op.create_index("ix_hr_pos_company", "hr_positions", ["company_id"])
    op.create_index("ix_hr_pos_department", "hr_positions", ["department_id"])

    op.create_table(
        "hr_shifts",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("start_time", sa.String(length=8), nullable=False),
        sa.Column("end_time", sa.String(length=8), nullable=False),
        sa.Column("break_minutes", sa.Numeric(6, 0), server_default="0", nullable=False),
        sa.Column("late_grace_minutes", sa.Numeric(6, 0), server_default="0", nullable=False),
        sa.Column("work_days", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", "code", name="uq_hr_shift_company_code"),
        *audit_columns(),
    )
    op.create_index("ix_hr_shift_company", "hr_shifts", ["company_id"])
    op.create_index("ix_hr_shift_branch", "hr_shifts", ["branch_id"])

    op.create_table(
        "hr_attendance_events",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shift_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=30), server_default="manual", nullable=False),
        sa.Column("device_identifier", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="recorded", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_id"], ["hr_shifts.id"], ondelete="SET NULL"),
        *audit_columns(),
    )
    op.create_index("ix_hr_att_company_time", "hr_attendance_events", ["company_id", "occurred_at"])
    op.create_index("ix_hr_att_employee_time", "hr_attendance_events", ["employee_id", "occurred_at"])

    op.create_table(
        "hr_leave_types",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("paid", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("annual_days", sa.Numeric(6, 2), server_default="0", nullable=False),
        sa.Column("requires_attachment", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("approval_levels", sa.Numeric(3, 0), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", "code", name="uq_hr_leave_type_company_code"),
        *audit_columns(),
    )
    op.create_index("ix_hr_leave_type_company", "hr_leave_types", ["company_id"])

    op.create_table(
        "hr_leave_requests",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days_requested", sa.Numeric(7, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("manager_comment", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["hr_leave_types.id"], ondelete="RESTRICT"),
        *audit_columns(),
    )
    op.create_index("ix_hr_leave_company_status", "hr_leave_requests", ["company_id", "status"])
    op.create_index("ix_hr_leave_employee_date", "hr_leave_requests", ["employee_id", "start_date"])

    op.create_table(
        "hr_payroll_runs",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_key", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("pay_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="LSL", nullable=False),
        sa.Column("gross_total", sa.Numeric(17, 2), server_default="0", nullable=False),
        sa.Column("deduction_total", sa.Numeric(17, 2), server_default="0", nullable=False),
        sa.Column("net_total", sa.Numeric(17, 2), server_default="0", nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", "period_key", name="uq_hr_payroll_company_period"),
        *audit_columns(),
    )
    op.create_index("ix_hr_payroll_company_status", "hr_payroll_runs", ["company_id", "status"])

    op.create_table(
        "hr_payroll_entries",
        sa.Column("payroll_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("basic_salary", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("allowances", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("overtime", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("deductions", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("tax", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("pension", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("gross_salary", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("net_salary", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payroll_run_id"], ["hr_payroll_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("payroll_run_id", "employee_id", name="uq_hr_payroll_entry_employee"),
        *audit_columns(),
    )
    op.create_index("ix_hr_pay_entry_run", "hr_payroll_entries", ["payroll_run_id"])
    op.create_index("ix_hr_pay_entry_employee", "hr_payroll_entries", ["employee_id"])

    op.create_table(
        "hr_vacancies",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("reference", sa.String(length=60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("openings", sa.Numeric(6, 0), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("closing_date", sa.Date(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["hr_departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["position_id"], ["hr_positions.id"], ondelete="SET NULL"),
        *audit_columns(),
    )
    op.create_index("ix_hr_vacancy_company_status", "hr_vacancies", ["company_id", "status"])
    op.create_index("ix_hr_vacancy_reference", "hr_vacancies", ["reference"])

    op.create_table(
        "hr_candidates",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.String(length=180), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("national_id", sa.String(length=80), nullable=True),
        sa.Column("stage", sa.String(length=40), server_default="applied", nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("application_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["hr_vacancies.id"], ondelete="SET NULL"),
        *audit_columns(),
    )
    op.create_index("ix_hr_candidate_company_stage", "hr_candidates", ["company_id", "stage"])
    op.create_index("ix_hr_candidate_vacancy", "hr_candidates", ["vacancy_id"])

    op.create_table(
        "hr_training_programs",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("provider", sa.String(length=160), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("capacity", sa.Numeric(6, 0), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="planned", nullable=False),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("cost", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), server_default="LSL", nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        *audit_columns(),
    )
    op.create_index("ix_hr_training_company_status", "hr_training_programs", ["company_id", "status"])

    op.create_table(
        "hr_training_enrollments",
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="registered", nullable=False),
        sa.Column("attendance_percent", sa.Numeric(6, 2), server_default="0", nullable=False),
        sa.Column("result", sa.String(length=80), nullable=True),
        sa.Column("certificate_reference", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["hr_training_programs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("program_id", "employee_id", name="uq_hr_training_employee"),
        *audit_columns(),
    )
    op.create_index("ix_hr_training_enroll_program", "hr_training_enrollments", ["program_id"])

    op.create_table(
        "hr_assets",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_tag", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("serial_number", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="available", nullable=False),
        sa.Column("condition", sa.String(length=40), server_default="good", nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_cost", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), server_default="LSL", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", "asset_tag", name="uq_hr_asset_company_tag"),
        *audit_columns(),
    )
    op.create_index("ix_hr_asset_company_status", "hr_assets", ["company_id", "status"])
    op.create_index("ix_hr_asset_branch", "hr_assets", ["branch_id"])

    op.create_table(
        "hr_asset_assignments",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_return_date", sa.Date(), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("condition_out", sa.String(length=40), nullable=True),
        sa.Column("condition_in", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="assigned", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["hr_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employee_profiles.id"], ondelete="RESTRICT"),
        *audit_columns(),
    )
    op.create_index("ix_hr_asset_assign_employee", "hr_asset_assignments", ["employee_id"])
    op.create_index("ix_hr_asset_assign_status", "hr_asset_assignments", ["company_id", "status"])

    op.add_column("employee_profiles", sa.Column("hr_department_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("employee_profiles", sa.Column("hr_position_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("employee_profiles", sa.Column("hr_shift_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("employee_profiles", sa.Column("national_id", sa.String(length=80), nullable=True))
    op.add_column("employee_profiles", sa.Column("passport_number", sa.String(length=80), nullable=True))
    op.add_column("employee_profiles", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("employee_profiles", sa.Column("contract_number", sa.String(length=100), nullable=True))
    op.add_column("employee_profiles", sa.Column("contract_start_date", sa.Date(), nullable=True))
    op.add_column("employee_profiles", sa.Column("contract_end_date", sa.Date(), nullable=True))
    op.add_column("employee_profiles", sa.Column("emergency_contacts", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("employee_profiles", sa.Column("qualifications", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("employee_profiles", sa.Column("certifications", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("employee_profiles", sa.Column("employment_history", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("employee_profiles", sa.Column("bank_name", sa.String(length=120), nullable=True))
    op.add_column("employee_profiles", sa.Column("bank_account_name", sa.String(length=160), nullable=True))
    op.add_column("employee_profiles", sa.Column("bank_account_number", sa.String(length=100), nullable=True))
    op.add_column("employee_profiles", sa.Column("tax_number", sa.String(length=100), nullable=True))
    op.add_column("employee_profiles", sa.Column("pension_number", sa.String(length=100), nullable=True))
    op.create_foreign_key("fk_emp_hr_department", "employee_profiles", "hr_departments", ["hr_department_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_emp_hr_position", "employee_profiles", "hr_positions", ["hr_position_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_emp_hr_shift", "employee_profiles", "hr_shifts", ["hr_shift_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_emp_hr_department", "employee_profiles", ["hr_department_id"])
    op.create_index("ix_emp_hr_position", "employee_profiles", ["hr_position_id"])
    op.create_index("ix_emp_hr_shift", "employee_profiles", ["hr_shift_id"])
    op.create_index("ix_emp_hr_national_id", "employee_profiles", ["national_id"])
    op.create_index("ix_emp_contract_end", "employee_profiles", ["contract_end_date"])


def downgrade() -> None:
    op.drop_index("ix_emp_contract_end", table_name="employee_profiles")
    op.drop_index("ix_emp_hr_national_id", table_name="employee_profiles")
    op.drop_index("ix_emp_hr_shift", table_name="employee_profiles")
    op.drop_index("ix_emp_hr_position", table_name="employee_profiles")
    op.drop_index("ix_emp_hr_department", table_name="employee_profiles")
    op.drop_constraint("fk_emp_hr_shift", "employee_profiles", type_="foreignkey")
    op.drop_constraint("fk_emp_hr_position", "employee_profiles", type_="foreignkey")
    op.drop_constraint("fk_emp_hr_department", "employee_profiles", type_="foreignkey")
    op.drop_column("employee_profiles", "pension_number")
    op.drop_column("employee_profiles", "tax_number")
    op.drop_column("employee_profiles", "bank_account_number")
    op.drop_column("employee_profiles", "bank_account_name")
    op.drop_column("employee_profiles", "bank_name")
    op.drop_column("employee_profiles", "employment_history")
    op.drop_column("employee_profiles", "certifications")
    op.drop_column("employee_profiles", "qualifications")
    op.drop_column("employee_profiles", "emergency_contacts")
    op.drop_column("employee_profiles", "contract_end_date")
    op.drop_column("employee_profiles", "contract_start_date")
    op.drop_column("employee_profiles", "contract_number")
    op.drop_column("employee_profiles", "date_of_birth")
    op.drop_column("employee_profiles", "passport_number")
    op.drop_column("employee_profiles", "national_id")
    op.drop_column("employee_profiles", "hr_shift_id")
    op.drop_column("employee_profiles", "hr_position_id")
    op.drop_column("employee_profiles", "hr_department_id")
    op.drop_index("ix_hr_asset_assign_status", table_name="hr_asset_assignments")
    op.drop_index("ix_hr_asset_assign_employee", table_name="hr_asset_assignments")
    op.drop_table("hr_asset_assignments")
    op.drop_index("ix_hr_asset_branch", table_name="hr_assets")
    op.drop_index("ix_hr_asset_company_status", table_name="hr_assets")
    op.drop_table("hr_assets")
    op.drop_index("ix_hr_training_enroll_program", table_name="hr_training_enrollments")
    op.drop_table("hr_training_enrollments")
    op.drop_index("ix_hr_training_company_status", table_name="hr_training_programs")
    op.drop_table("hr_training_programs")
    op.drop_index("ix_hr_candidate_vacancy", table_name="hr_candidates")
    op.drop_index("ix_hr_candidate_company_stage", table_name="hr_candidates")
    op.drop_table("hr_candidates")
    op.drop_index("ix_hr_vacancy_reference", table_name="hr_vacancies")
    op.drop_index("ix_hr_vacancy_company_status", table_name="hr_vacancies")
    op.drop_table("hr_vacancies")
    op.drop_index("ix_hr_pay_entry_employee", table_name="hr_payroll_entries")
    op.drop_index("ix_hr_pay_entry_run", table_name="hr_payroll_entries")
    op.drop_table("hr_payroll_entries")
    op.drop_index("ix_hr_payroll_company_status", table_name="hr_payroll_runs")
    op.drop_table("hr_payroll_runs")
    op.drop_index("ix_hr_leave_employee_date", table_name="hr_leave_requests")
    op.drop_index("ix_hr_leave_company_status", table_name="hr_leave_requests")
    op.drop_table("hr_leave_requests")
    op.drop_index("ix_hr_leave_type_company", table_name="hr_leave_types")
    op.drop_table("hr_leave_types")
    op.drop_index("ix_hr_att_employee_time", table_name="hr_attendance_events")
    op.drop_index("ix_hr_att_company_time", table_name="hr_attendance_events")
    op.drop_table("hr_attendance_events")
    op.drop_index("ix_hr_shift_branch", table_name="hr_shifts")
    op.drop_index("ix_hr_shift_company", table_name="hr_shifts")
    op.drop_table("hr_shifts")
    op.drop_index("ix_hr_pos_department", table_name="hr_positions")
    op.drop_index("ix_hr_pos_company", table_name="hr_positions")
    op.drop_table("hr_positions")
    op.drop_index("ix_hr_dept_active", table_name="hr_departments")
    op.drop_index("ix_hr_dept_branch", table_name="hr_departments")
    op.drop_index("ix_hr_dept_company", table_name="hr_departments")
    op.drop_table("hr_departments")
