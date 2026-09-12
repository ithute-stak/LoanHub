"""align legacy index names and restore the selected-offer foreign key

Revision ID: d4e7b6c1a930
Revises: b84d1f2a9c30
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d4e7b6c1a930"
down_revision: Union[str, Sequence[str], None] = "b84d1f2a9c30"
branch_labels = None
depends_on = None


INDEX_RENAMES = (
    ("ix_client_loan_borrower_id", "ix_client_company_loan_borrower_id"),
    ("ix_client_loan_branch_id", "ix_client_company_loan_branch_id"),
    ("ix_client_loan_company_id", "ix_client_company_loan_company_id"),
    ("ix_loan_offers_request_id", "ix_loan_offers_loan_request_id"),
    ("ix_marketplace_unlock_company", "ix_marketplace_unlocks_company_id"),
    ("ix_marketplace_unlock_request", "ix_marketplace_unlocks_loan_request_id"),
    ("ix_payment_allocation_installment", "ix_payment_allocations_installment_id"),
    ("ix_payment_allocation_payment", "ix_payment_allocations_payment_id"),
    ("ix_payment_borrower_id", "ix_payment_transactions_borrower_id"),
    ("ix_payment_company_id", "ix_payment_transactions_company_id"),
    ("ix_payment_idempotency", "ix_payment_transactions_idempotency_key"),
    ("ix_payment_loan_id", "ix_payment_transactions_loan_id"),
    ("ix_payment_loan_request_id", "ix_payment_transactions_loan_request_id"),
    ("ix_payment_provider_reference", "ix_payment_transactions_provider_reference"),
    ("ix_repayment_installment_due", "ix_repayment_installments_due_date"),
    ("ix_repayment_installment_loan", "ix_repayment_installments_loan_id"),
)


def _normalize_index_name(old_name: str, new_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass(
                current_schema() || '.{old_name}'
            ) IS NOT NULL THEN
                IF to_regclass(
                    current_schema() || '.{new_name}'
                ) IS NULL THEN
                    ALTER INDEX {old_name}
                    RENAME TO {new_name};
                ELSE
                    DROP INDEX {old_name};
                END IF;
            END IF;
        END
        $$;
        """
    )


def _drop_selected_offer_foreign_keys() -> None:
    op.execute(
        """
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
                   AND source_table.relname = 'loan_requests'
                   AND constraint_row.confrelid =
                       'loan_offers'::regclass
                   AND EXISTS (
                        SELECT 1
                          FROM unnest(constraint_row.conkey)
                               AS key_column(attnum)
                          JOIN pg_attribute AS attribute_row
                            ON attribute_row.attrelid =
                               constraint_row.conrelid
                           AND attribute_row.attnum =
                               key_column.attnum
                         WHERE attribute_row.attname =
                               'selected_offer_id'
                   )
            LOOP
                EXECUTE format(
                    'ALTER TABLE loan_requests '
                    'DROP CONSTRAINT %I',
                    item.conname
                );
            END LOOP;
        END
        $$;
        """
    )


def _create_selected_offer_foreign_key() -> None:
    _drop_selected_offer_foreign_keys()

    op.create_foreign_key(
        "loan_requests_selected_offer_id_fkey",
        "loan_requests",
        "loan_offers",
        ["selected_offer_id"],
        ["id"],
        ondelete="SET NULL",
    )


def upgrade() -> None:
    op.execute(
        "SELECT pg_advisory_xact_lock(62106420260717)"
    )
    op.execute("SET LOCAL lock_timeout = '60s'")
    op.execute("SET LOCAL statement_timeout = '20min'")

    for old_name, new_name in INDEX_RENAMES:
        _normalize_index_name(
            old_name,
            new_name,
        )

    _create_selected_offer_foreign_key()


def downgrade() -> None:
    _drop_selected_offer_foreign_keys()

    for old_name, new_name in reversed(
        INDEX_RENAMES,
    ):
        _normalize_index_name(
            new_name,
            old_name,
        )
