"""Employer groups and borrower income-day classification.

Revision ID: a1b2c3d4e910
Revises: z9n3p5q7r800
Create Date: 2026-09-08
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a1b2c3d4e910"
down_revision: Union[str, Sequence[str], None] = "z9n3p5q7r800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SEEDED_GROUPS = (
    ("10000000-0000-0000-0000-000000000001", "L/GOV", "Lesotho Government"),
    ("10000000-0000-0000-0000-000000000002", "LMPS", "Lesotho Mounted Police Service"),
    ("10000000-0000-0000-0000-000000000003", "LCS", "Lesotho Correctional Service"),
    ("10000000-0000-0000-0000-000000000004", "LDF", "Lesotho Defence Force"),
    ("10000000-0000-0000-0000-000000000005", "NSS", "National Security Service"),
    ("10000000-0000-0000-0000-000000000006", "NDSO", "NDSO"),
    ("10000000-0000-0000-0000-000000000007", "PENSIONS", "Pensions"),
    ("10000000-0000-0000-0000-000000000008", "NGO", "NGO"),
    ("10000000-0000-0000-0000-000000000009", "LEMS", "LEMS"),
    ("10000000-0000-0000-0000-000000000010", "LE HAE", "LE HAE"),
)


def upgrade() -> None:
    op.create_table(
        "employer_groups",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_employer_groups_code"),
    )
    op.create_index("ix_employer_groups_code", "employer_groups", ["code"], unique=False)
    op.create_index("ix_employer_groups_name", "employer_groups", ["name"], unique=False)
    op.create_index("ix_employer_groups_is_active", "employer_groups", ["is_active"], unique=False)

    employer_groups = sa.table(
        "employer_groups",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        employer_groups,
        [
            {"id": uuid.UUID(group_id), "code": code, "name": name, "is_active": True}
            for group_id, code, name in _SEEDED_GROUPS
        ],
    )

    op.add_column(
        "borrowers",
        sa.Column("employer_group_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "borrowers",
        sa.Column("income_day", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_borrowers_employer_group_id",
        "borrowers",
        "employer_groups",
        ["employer_group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_borrowers_employer_group_id",
        "borrowers",
        ["employer_group_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_borrowers_income_day",
        "borrowers",
        "income_day IS NULL OR (income_day >= 1 AND income_day <= 31)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_borrowers_income_day", "borrowers", type_="check")
    op.drop_index("ix_borrowers_employer_group_id", table_name="borrowers")
    op.drop_constraint("fk_borrowers_employer_group_id", "borrowers", type_="foreignkey")
    op.drop_column("borrowers", "income_day")
    op.drop_column("borrowers", "employer_group_id")
    op.drop_index("ix_employer_groups_is_active", table_name="employer_groups")
    op.drop_index("ix_employer_groups_name", table_name="employer_groups")
    op.drop_index("ix_employer_groups_code", table_name="employer_groups")
    op.drop_table("employer_groups")
