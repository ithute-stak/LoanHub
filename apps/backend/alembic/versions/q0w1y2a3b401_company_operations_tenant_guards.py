"""add tenant guards for specialised company operations

Revision ID: q0w1y2a3b401
Revises: p9v0x1z2a301
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op

revision = "q0w1y2a3b401"
down_revision = "p9v0x1z2a301"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_company_operation_borrower_scope()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.borrower_id IS NULL THEN
                RETURN NEW;
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM company_borrower_accounts cba
                WHERE cba.company_id = NEW.company_id
                  AND cba.borrower_id = NEW.borrower_id
            ) AND NOT EXISTS (
                SELECT 1
                FROM client_company_loan loan
                WHERE loan.company_id = NEW.company_id
                  AND loan.borrower_id = NEW.borrower_id
            ) THEN
                RAISE EXCEPTION 'Borrower is outside the active company scope';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("crm_relationship_cases", "collateral_assets", "legal_recovery_matters", "customer_complaint_cases"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_borrower_scope
            BEFORE INSERT OR UPDATE OF company_id, borrower_id ON {table}
            FOR EACH ROW EXECUTE FUNCTION enforce_company_operation_borrower_scope();
            """
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_company_operation_assignee_scope()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.assigned_user_id IS NULL THEN
                RETURN NEW;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM company_staff staff
                WHERE staff.company_id = NEW.company_id
                  AND staff.user_id = NEW.assigned_user_id
                  AND staff.is_active IS TRUE
                  AND (NEW.branch_id IS NULL OR staff.branch_id IS NULL OR staff.branch_id = NEW.branch_id)
            ) THEN
                RAISE EXCEPTION 'Assigned user is outside the active company/branch scope';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in ("crm_relationship_cases", "legal_recovery_matters", "customer_complaint_cases"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_assignee_scope
            BEFORE INSERT OR UPDATE OF company_id, branch_id, assigned_user_id ON {table}
            FOR EACH ROW EXECUTE FUNCTION enforce_company_operation_assignee_scope();
            """
        )


def downgrade() -> None:
    for table in ("crm_relationship_cases", "legal_recovery_matters", "customer_complaint_cases"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_assignee_scope ON {table};")
    op.execute("DROP FUNCTION IF EXISTS enforce_company_operation_assignee_scope();")
    for table in ("crm_relationship_cases", "collateral_assets", "legal_recovery_matters", "customer_complaint_cases"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_borrower_scope ON {table};")
    op.execute("DROP FUNCTION IF EXISTS enforce_company_operation_borrower_scope();")
