"""Payment engine policy settings (opt-in; no live loan changes).

Revision ID: p6a1r2p3o901
Revises: r8l1m2r6f477
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p6a1r2p3o901"
down_revision = "r8l1m2r6f477"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_loan_settings", sa.Column("arrears_policy", postgresql.JSONB(), nullable=True))
    op.add_column("loan_products", sa.Column("arrears_policy_override", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("loan_products", "arrears_policy_override")
    op.drop_column("company_loan_settings", "arrears_policy")
