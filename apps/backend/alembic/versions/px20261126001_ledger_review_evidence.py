"""Persist Principal x ledger review evidence.

Revision ID: px20261126001
Revises: bc20261124001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "px20261126001"
down_revision = "bc20261124001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "principal_x_ledger_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("updated_by", sa.String(36)),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client_company_loan.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("maker_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("checker_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("review_reference", sa.String(180), nullable=False),
        sa.Column("source_revision", sa.String(64), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("net_collected", sa.Numeric(15, 2), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attestations", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("company_id", "review_reference", name="uq_px_review_reference"),
        sa.CheckConstraint("maker_user_id <> checker_user_id", name="ck_px_review_independent"),
        sa.CheckConstraint("net_collected >= 0", name="ck_px_review_nonnegative"),
        sa.CheckConstraint("source_revision ~ '^[0-9a-f]{64}$'", name="ck_px_review_revision"),
        sa.CheckConstraint("evidence_digest ~ '^[0-9a-f]{64}$'", name="ck_px_review_digest"),
        sa.CheckConstraint("jsonb_typeof(attestations) = 'array' AND jsonb_array_length(attestations) = 8", name="ck_px_review_sources"),
    )
    op.create_index("ix_principal_x_ledger_reviews_company_id", "principal_x_ledger_reviews", ["company_id"])
    op.create_index("ix_principal_x_ledger_reviews_loan_id", "principal_x_ledger_reviews", ["loan_id"])
    op.execute("""
        CREATE FUNCTION px_ledger_review_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'Principal x ledger reviews are append-only';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM client_company_loan
                WHERE id = NEW.loan_id AND company_id = NEW.company_id
            ) THEN
                RAISE EXCEPTION 'Principal x review loan scope mismatch';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER px_ledger_review_row_guard
        BEFORE INSERT OR UPDATE OR DELETE ON principal_x_ledger_reviews
        FOR EACH ROW EXECUTE FUNCTION px_ledger_review_guard()
    """)
    op.execute("""
        CREATE TRIGGER px_ledger_review_truncate_guard
        BEFORE TRUNCATE ON principal_x_ledger_reviews
        FOR EACH STATEMENT EXECUTE FUNCTION px_ledger_review_guard()
    """)


def downgrade():
    # Never silently destroy retained financial evidence.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM principal_x_ledger_reviews) THEN
                RAISE EXCEPTION 'Cannot downgrade populated Principal x review ledger';
            END IF;
        END $$;
    """)
    op.drop_table("principal_x_ledger_reviews")
    op.execute("DROP FUNCTION px_ledger_review_guard()")
