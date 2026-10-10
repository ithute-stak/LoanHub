"""Reclassify BFS loan folios by contractual pay date.

Revision ID: h5j9l1n3p567
Revises: g4i8k0m2n456
Create Date: 2026-10-10
"""

from typing import Sequence, Union

from alembic import op


revision: str = "h5j9l1n3p567"
down_revision: Union[str, Sequence[str], None] = "g4i8k0m2n456"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The original folio sequence was scoped to employer/work-group. BFS now
    # operates three pay-date sequence books:
    #   15-22 => Force
    #   23-26 => CIVIL
    #   27-31 => S/E
    #
    # Re-number all existing BFS rows in deterministic creation order. The
    # unique sequence constraint is dropped only inside this migration
    # transaction so rows can move safely between sequence books.
    op.execute(
        """
        ALTER TABLE client_company_loan
        DROP CONSTRAINT IF EXISTS uq_client_loan_folio_sequence
        """
    )

    op.execute(
        """
        WITH source AS (
            SELECT
                l.id,
                l.company_id,
                COALESCE(
                    NULLIF(l.preferred_payment_day, 0),
                    EXTRACT(DAY FROM l.first_payment_due)::integer,
                    CASE
                        WHEN (l.calculation_breakdown #>> '{schedule_rows,0,due_date}')
                             ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}                        THEN EXTRACT(
                            DAY FROM (l.calculation_breakdown #>> '{schedule_rows,0,due_date}')::date
                        )::integer
                        ELSE NULL
                    END
                ) AS pay_day,
                l.created_at
            FROM client_company_loan AS l
            WHERE l.folio_company_code = 'BFS'
        ),
        classified AS (
            SELECT
                id,
                company_id,
                created_at,
                CASE
                    WHEN pay_day BETWEEN 15 AND 22 THEN 'Force'
                    WHEN pay_day BETWEEN 23 AND 26 THEN 'CIVIL'
                    WHEN pay_day BETWEEN 27 AND 31 THEN 'S/E'
                    ELSE NULL
                END AS new_group
            FROM source
        ),
        numbered AS (
            SELECT
                id,
                new_group,
                ROW_NUMBER() OVER (
                    PARTITION BY company_id, new_group
                    ORDER BY created_at, id
                )::integer AS new_sequence
            FROM classified
            WHERE new_group IS NOT NULL
        )
        UPDATE client_company_loan AS l
        SET
            folio_group_code = n.new_group,
            folio_sequence = n.new_sequence,
            folio_number = l.folio_company_code || '-' || n.new_group || '-' || LPAD(n.new_sequence::text, 5, '0')
        FROM numbered AS n
        WHERE l.id = n.id
        """
    )

    op.create_unique_constraint(
        "uq_client_loan_folio_sequence",
        "client_company_loan",
        ["company_id", "folio_group_code", "folio_sequence"],
    )


def downgrade() -> None:
    # This is a business-data reclassification. The former employer-derived
    # folio identity is not retained after the approved renumbering, so a
    # downgrade intentionally leaves the new folio identities in place.
    pass

                        THEN EXTRACT(
                            DAY FROM (l.calculation_breakdown #>> '{schedule_rows,0,due_date}')::date
                        )::integer
                        ELSE NULL
                    END
                ) AS pay_day,
                l.created_at
            FROM client_company_loan AS l
            WHERE l.folio_company_code = 'BFS'
        ),
        classified AS (
            SELECT
                id,
                company_id,
                created_at,
                CASE
                    WHEN pay_day BETWEEN 15 AND 22 THEN 'Force'
                    WHEN pay_day BETWEEN 23 AND 26 THEN 'CIVIL'
                    WHEN pay_day BETWEEN 27 AND 31 THEN 'S/E'
                    ELSE NULL
                END AS new_group
            FROM source
        ),
        numbered AS (
            SELECT
                id,
                new_group,
                ROW_NUMBER() OVER (
                    PARTITION BY company_id, new_group
                    ORDER BY created_at, id
                )::integer AS new_sequence
            FROM classified
            WHERE new_group IS NOT NULL
        )
        UPDATE client_company_loan AS l
        SET
            folio_group_code = n.new_group,
            folio_sequence = n.new_sequence,
            folio_number = l.folio_company_code || '-' || n.new_group || '-' || LPAD(n.new_sequence::text, 5, '0')
        FROM numbered AS n
        WHERE l.id = n.id
        """
    )

    op.create_unique_constraint(
        "uq_client_loan_folio_sequence",
        "client_company_loan",
        ["company_id", "folio_group_code", "folio_sequence"],
    )


def downgrade() -> None:
    # This is a business-data reclassification. The former employer-derived
    # folio identity is not retained after the approved renumbering, so a
    # downgrade intentionally leaves the new folio identities in place.
    pass

                        THEN EXTRACT(
                            DAY FROM (l.calculation_breakdown #>> '{schedule_rows,0,due_date}')::date
                        )::integer
                        ELSE NULL
                    END
                ) AS pay_day,
                l.created_at
            FROM client_company_loan AS l
            WHERE l.folio_company_code = 'BFS'
        ),
        classified AS (
            SELECT
                id,
                company_id,
                created_at,
                CASE
                    WHEN pay_day BETWEEN 15 AND 22 THEN 'Force'
                    WHEN pay_day BETWEEN 23 AND 26 THEN 'CIVIL'
                    WHEN pay_day BETWEEN 27 AND 31 THEN 'S/E'
                    ELSE NULL
                END AS new_group
            FROM source
        ),
        numbered AS (
            SELECT
                id,
                new_group,
                ROW_NUMBER() OVER (
                    PARTITION BY company_id, new_group
                    ORDER BY created_at, id
                )::integer AS new_sequence
            FROM classified
            WHERE new_group IS NOT NULL
        )
        UPDATE client_company_loan AS l
        SET
            folio_group_code = n.new_group,
            folio_sequence = n.new_sequence,
            folio_number = l.folio_company_code || '-' || n.new_group || '-' || LPAD(n.new_sequence::text, 5, '0')
        FROM numbered AS n
        WHERE l.id = n.id
        """
    )

    op.create_unique_constraint(
        "uq_client_loan_folio_sequence",
        "client_company_loan",
        ["company_id", "folio_group_code", "folio_sequence"],
    )


def downgrade() -> None:
    # This is a business-data reclassification. The former employer-derived
    # folio identity is not retained after the approved renumbering, so a
    # downgrade intentionally leaves the new folio identities in place.
    pass

                        THEN EXTRACT(
                            DAY FROM (l.calculation_breakdown #>> '{schedule_rows,0,due_date}')::date
                        )::integer
                        ELSE NULL
                    END
                ) AS pay_day,
                l.created_at
            FROM client_company_loan AS l
            WHERE l.folio_company_code = 'BFS'
        ),
        classified AS (
            SELECT
                id,
                company_id,
                created_at,
                CASE
                    WHEN pay_day BETWEEN 15 AND 22 THEN 'Force'
                    WHEN pay_day BETWEEN 23 AND 26 THEN 'CIVIL'
                    WHEN pay_day BETWEEN 27 AND 31 THEN 'S/E'
                    ELSE NULL
                END AS new_group
            FROM source
        ),
        numbered AS (
            SELECT
                id,
                new_group,
                ROW_NUMBER() OVER (
                    PARTITION BY company_id, new_group
                    ORDER BY created_at, id
                )::integer AS new_sequence
            FROM classified
            WHERE new_group IS NOT NULL
        )
        UPDATE client_company_loan AS l
        SET
            folio_group_code = n.new_group,
            folio_sequence = n.new_sequence,
            folio_number = l.folio_company_code || '-' || n.new_group || '-' || LPAD(n.new_sequence::text, 5, '0')
        FROM numbered AS n
        WHERE l.id = n.id
        """
    )

    op.create_unique_constraint(
        "uq_client_loan_folio_sequence",
        "client_company_loan",
        ["company_id", "folio_group_code", "folio_sequence"],
    )


def downgrade() -> None:
    # This is a business-data reclassification. The former employer-derived
    # folio identity is not retained after the approved renumbering, so a
    # downgrade intentionally leaves the new folio identities in place.
    pass
