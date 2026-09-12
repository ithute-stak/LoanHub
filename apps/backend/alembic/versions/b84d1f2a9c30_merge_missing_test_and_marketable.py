"""canonical schema repair after compatibility and marketable revisions

Revision ID: b84d1f2a9c30
Revises: 8d2f4a1b7c90
Create Date: 2026-07-15

This revision canonicalizes installations that may previously have applied the\naccidental local revision or the marketable feature branch independently.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b84d1f2a9c30"
down_revision: Union[str, Sequence[str], None] = "8d2f4a1b7c90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Restore Base.created_by after PerformanceGoal's relationship naming bug
    # caused Alembic to treat this inherited column as removed.
    op.execute(
        "ALTER TABLE performance_goals "
        "ADD COLUMN IF NOT EXISTS created_by VARCHAR(36)"
    )

    # The accidental migration converted the fingerprint unique constraint
    # into a unique index. Convert it back to one canonical unique constraint.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'system_error_logs_fingerprint_key'
                  AND conrelid = 'system_error_logs'::regclass
            ) THEN
                IF EXISTS (
                    SELECT 1
                    FROM pg_class index_class
                    JOIN pg_index index_info
                      ON index_info.indexrelid = index_class.oid
                    JOIN pg_class table_class
                      ON table_class.oid = index_info.indrelid
                    WHERE index_class.relname = 'ix_system_error_logs_fingerprint'
                      AND table_class.relname = 'system_error_logs'
                      AND index_info.indisunique
                ) THEN
                    ALTER TABLE system_error_logs
                    ADD CONSTRAINT system_error_logs_fingerprint_key
                    UNIQUE USING INDEX ix_system_error_logs_fingerprint;
                ELSE
                    ALTER TABLE system_error_logs
                    ADD CONSTRAINT system_error_logs_fingerprint_key
                    UNIQUE (fingerprint);
                END IF;
            END IF;
        END
        $$;
        """
    )

    # Remove a redundant standalone index only when it is not owned by a
    # PostgreSQL constraint. An index attached with UNIQUE USING INDEX must stay.
    op.execute(
        """
        DO $$
        DECLARE
            target_index_oid OID;
        BEGIN
            SELECT c.oid
              INTO target_index_oid
              FROM pg_class c
             WHERE c.relname = 'ix_system_error_logs_fingerprint'
               AND c.relkind = 'i';

            IF target_index_oid IS NOT NULL
               AND NOT EXISTS (
                    SELECT 1
                      FROM pg_constraint
                     WHERE conindid = target_index_oid
               ) THEN
                DROP INDEX ix_system_error_logs_fingerprint;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Revision 8d2f4a1b7c90 already contains the canonical created_by column
    # and fingerprint unique constraint. Recreate only the redundant legacy
    # lookup index that this repair removes during upgrade.
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_system_error_logs_fingerprint "
        "ON system_error_logs (fingerprint)"
    )
