"""allow imported payroll rows pending reconciliation

Revision ID: g1m2p3r4s502
Revises: g1m2p3r4s501
Create Date: 2026-09-26
"""

from __future__ import annotations

from alembic import op


revision = "g1m2p3r4s502"
down_revision = "g1m2p3r4s501"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_employer_payroll_deduction_status",
        "employer_payroll_deductions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_employer_payroll_deduction_status",
        "employer_payroll_deductions",
        "status IN ('pending','received','matched','shortage','excess','rejected','missing','terminated','unmatched')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_employer_payroll_deduction_status",
        "employer_payroll_deductions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_employer_payroll_deduction_status",
        "employer_payroll_deductions",
        "status IN ('pending','matched','shortage','excess','rejected','missing','terminated','unmatched')",
    )
