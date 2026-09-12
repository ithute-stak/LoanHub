"""normalize company staff company cascade

Revision ID: 307dcdf0187c
Revises: 9f1c2d3e4a5b
"""

from typing import Sequence, Union

from alembic import op


revision: str = "307dcdf0187c"
down_revision: Union[str, Sequence[str], None] = "9f1c2d3e4a5b"
branch_labels = None
depends_on = None


def _replace_company_foreign_key(on_delete: str | None) -> None:
    delete_clause = (
        f" ON DELETE {on_delete}"
        if on_delete
        else ""
    )

    op.execute(
        f"""
        DO $$
        DECLARE
            item RECORD;
        BEGIN
            FOR item IN
                SELECT constraint_row.conname
                  FROM pg_constraint AS constraint_row
                  JOIN pg_class AS source_table
                    ON source_table.oid = constraint_row.conrelid
                  JOIN pg_namespace AS source_schema
                    ON source_schema.oid = source_table.relnamespace
                 WHERE constraint_row.contype = 'f'
                   AND source_schema.nspname = current_schema()
                   AND source_table.relname = 'company_staff'
                   AND constraint_row.confrelid =
                       'loan_companies'::regclass
                   AND EXISTS (
                        SELECT 1
                          FROM unnest(constraint_row.conkey)
                               AS key_column(attnum)
                          JOIN pg_attribute AS attribute_row
                            ON attribute_row.attrelid =
                               constraint_row.conrelid
                           AND attribute_row.attnum =
                               key_column.attnum
                         WHERE attribute_row.attname = 'company_id'
                   )
            LOOP
                EXECUTE format(
                    'ALTER TABLE company_staff DROP CONSTRAINT %I',
                    item.conname
                );
            END LOOP;

            ALTER TABLE company_staff
            ADD CONSTRAINT company_staff_company_id_fkey
            FOREIGN KEY (company_id)
            REFERENCES loan_companies (id){delete_clause};
        END
        $$;
        """
    )


def upgrade() -> None:
    _replace_company_foreign_key("CASCADE")


def downgrade() -> None:
    _replace_company_foreign_key(None)
