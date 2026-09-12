"""add people model

Revision ID: 7ba90e8af6b6
Revises: fd4aa8a11b41
Create Date: 2026-07-13 18:53:45.637153
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Revision identifiers used by Alembic.
revision: str = "7ba90e8af6b6"

down_revision: Union[
    str,
    Sequence[str],
    None,
] = "fd4aa8a11b41"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


# These PostgreSQL enum types already exist because they were
# previously used by the borrowers table.
#
# create_type=False prevents Alembic from issuing:
#
# CREATE TYPE gender ...
# CREATE TYPE maritalstatus ...
gender_enum = postgresql.ENUM(
    "MALE",
    "FEMALE",
    "OTHER",
    name="gender",
    create_type=False,
)

marital_status_enum = postgresql.ENUM(
    "SINGLE",
    "MARRIED",
    "DIVORCED",
    "WIDOWED",
    name="maritalstatus",
    create_type=False,
)


def upgrade() -> None:
    connection = op.get_bind()

    # ---------------------------------------------------------
    # 1. Create people table using existing PostgreSQL enums
    # ---------------------------------------------------------

    op.create_table(
        "people",

        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "first_name",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "middle_name",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "last_name",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "gender",
            gender_enum,
            nullable=True,
        ),

        sa.Column(
            "date_of_birth",
            sa.Date(),
            nullable=True,
        ),

        sa.Column(
            "national_id",
            sa.String(length=50),
            nullable=True,
        ),

        sa.Column(
            "passport_number",
            sa.String(length=50),
            nullable=True,
        ),

        sa.Column(
            "marital_status",
            marital_status_enum,
            nullable=True,
        ),

        sa.Column(
            "nationality",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "district",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "town_or_village",
            sa.String(length=150),
            nullable=True,
        ),

        sa.Column(
            "physical_address",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.Column(
            "created_by",
            sa.String(length=36),
            nullable=True,
        ),

        sa.Column(
            "updated_by",
            sa.String(length=36),
            nullable=True,
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_people_user_id_users",
            ondelete="CASCADE",
        ),

        sa.PrimaryKeyConstraint(
            "id",
            name="pk_people",
        ),
    )

    op.create_index(
        "ix_people_user_id",
        "people",
        ["user_id"],
        unique=True,
    )

    op.create_index(
        "ix_people_national_id",
        "people",
        ["national_id"],
        unique=True,
    )

    op.create_index(
        "ix_people_passport_number",
        "people",
        ["passport_number"],
        unique=True,
    )

    # ---------------------------------------------------------
    # 2. Copy existing borrower personal data into people
    # ---------------------------------------------------------

    # Use one set-based SQL statement so this migration works in normal
    # online execution and in ``alembic upgrade --sql`` offline validation.
    # The borrower UUID is safe to reuse because ``people`` is new and empty.
    connection.execute(
        sa.text(
            """
            INSERT INTO people (
                id,
                user_id,
                first_name,
                middle_name,
                last_name,
                gender,
                date_of_birth,
                national_id,
                passport_number,
                marital_status,
                nationality,
                district,
                town_or_village,
                physical_address,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            SELECT
                id,
                user_id,
                first_name,
                middle_name,
                last_name,
                gender,
                date_of_birth,
                national_id,
                passport_number,
                marital_status,
                nationality,
                district,
                town_or_village,
                physical_address,
                COALESCE(created_at, NOW()),
                COALESCE(updated_at, NOW()),
                created_by,
                updated_by
            FROM borrowers
            """
        )
    )

    # Confirm that every borrower received a person record before
    # deleting personal columns from borrowers.
    connection.execute(
        sa.text(
            """
            DO $$
            DECLARE
                missing_count BIGINT;
            BEGIN
                SELECT COUNT(*)
                  INTO missing_count
                  FROM borrowers AS borrower
                  LEFT JOIN people AS person
                    ON person.user_id = borrower.user_id
                 WHERE person.id IS NULL;

                IF missing_count > 0 THEN
                    RAISE EXCEPTION
                        '% borrower records were not copied into people',
                        missing_count;
                END IF;
            END
            $$;
            """
        )
    )

    # ---------------------------------------------------------
    # 3. Fill nullable boolean and amount columns
    # ---------------------------------------------------------

    connection.execute(
        sa.text(
            """
            UPDATE borrowers
            SET has_existing_loans = FALSE
            WHERE has_existing_loans IS NULL
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE borrowers
            SET existing_loan_total = 0
            WHERE existing_loan_total IS NULL
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE borrowers
            SET consent_to_share_profile = FALSE
            WHERE consent_to_share_profile IS NULL
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE borrowers
            SET consent_to_credit_checks = FALSE
            WHERE consent_to_credit_checks IS NULL
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE refresh_tokens
            SET revoked = FALSE
            WHERE revoked IS NULL
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE users
            SET is_active = TRUE
            WHERE is_active IS NULL
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE users
            SET is_verified = FALSE
            WHERE is_verified IS NULL
            """
        )
    )

    # ---------------------------------------------------------
    # 4. Apply NOT NULL constraints
    # ---------------------------------------------------------

    op.alter_column(
        "borrowers",
        "has_existing_loans",
        existing_type=sa.Boolean(),
        nullable=False,
    )

    op.alter_column(
        "borrowers",
        "existing_loan_total",
        existing_type=sa.Numeric(
            precision=12,
            scale=2,
        ),
        nullable=False,
    )

    op.alter_column(
        "borrowers",
        "consent_to_share_profile",
        existing_type=sa.Boolean(),
        nullable=False,
    )

    op.alter_column(
        "borrowers",
        "consent_to_credit_checks",
        existing_type=sa.Boolean(),
        nullable=False,
    )

    op.alter_column(
        "refresh_tokens",
        "revoked",
        existing_type=sa.Boolean(),
        nullable=False,
    )

    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
    )

    op.alter_column(
        "users",
        "is_verified",
        existing_type=sa.Boolean(),
        nullable=False,
    )

    # ---------------------------------------------------------
    # 5. Update borrower user relationship constraints
    # ---------------------------------------------------------

    op.drop_constraint(
        "borrowers_national_id_key",
        "borrowers",
        type_="unique",
    )

    op.drop_constraint(
        "borrowers_passport_number_key",
        "borrowers",
        type_="unique",
    )

    op.drop_constraint(
        "borrowers_user_id_key",
        "borrowers",
        type_="unique",
    )

    op.create_index(
        "ix_borrowers_user_id",
        "borrowers",
        ["user_id"],
        unique=True,
    )

    op.drop_constraint(
        "borrowers_user_id_fkey",
        "borrowers",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_borrowers_user_id_users",
        "borrowers",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ---------------------------------------------------------
    # 6. Remove duplicated personal fields from borrowers
    # ---------------------------------------------------------

    op.drop_column(
        "borrowers",
        "nationality",
    )

    op.drop_column(
        "borrowers",
        "date_of_birth",
    )

    op.drop_column(
        "borrowers",
        "gender",
    )

    op.drop_column(
        "borrowers",
        "passport_number",
    )

    op.drop_column(
        "borrowers",
        "physical_address",
    )

    op.drop_column(
        "borrowers",
        "national_id",
    )

    op.drop_column(
        "borrowers",
        "district",
    )

    op.drop_column(
        "borrowers",
        "town_or_village",
    )

    op.drop_column(
        "borrowers",
        "first_name",
    )

    op.drop_column(
        "borrowers",
        "last_name",
    )

    op.drop_column(
        "borrowers",
        "middle_name",
    )

    op.drop_column(
        "borrowers",
        "marital_status",
    )


def downgrade() -> None:
    connection = op.get_bind()

    # ---------------------------------------------------------
    # 1. Restore personal columns temporarily as nullable
    # ---------------------------------------------------------

    op.add_column(
        "borrowers",
        sa.Column(
            "marital_status",
            marital_status_enum,
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "middle_name",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "last_name",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "first_name",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "town_or_village",
            sa.String(length=150),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "district",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "national_id",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "physical_address",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "passport_number",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "gender",
            gender_enum,
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "date_of_birth",
            sa.Date(),
            nullable=True,
        ),
    )

    op.add_column(
        "borrowers",
        sa.Column(
            "nationality",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # 2. Copy people data back into borrowers
    # ---------------------------------------------------------

    connection.execute(
        sa.text(
            """
            UPDATE borrowers AS borrower
            SET
                first_name = person.first_name,
                middle_name = person.middle_name,
                last_name = person.last_name,
                gender = person.gender,
                date_of_birth = person.date_of_birth,
                national_id = person.national_id,
                passport_number = person.passport_number,
                marital_status = person.marital_status,
                nationality = person.nationality,
                district = person.district,
                town_or_village = person.town_or_village,
                physical_address = person.physical_address
            FROM people AS person
            WHERE person.user_id = borrower.user_id
            """
        )
    )

    connection.execute(
        sa.text(
            """
            DO $$
            DECLARE
                missing_count BIGINT;
            BEGIN
                SELECT COUNT(*)
                  INTO missing_count
                  FROM borrowers
                 WHERE first_name IS NULL
                    OR last_name IS NULL
                    OR gender IS NULL
                    OR date_of_birth IS NULL
                    OR district IS NULL;

                IF missing_count > 0 THEN
                    RAISE EXCEPTION
                        '% borrowers do not have complete person profiles',
                        missing_count;
                END IF;
            END
            $$;
            """
        )
    )

    op.alter_column(
        "borrowers",
        "first_name",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    op.alter_column(
        "borrowers",
        "last_name",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    op.alter_column(
        "borrowers",
        "gender",
        existing_type=gender_enum,
        nullable=False,
    )

    op.alter_column(
        "borrowers",
        "date_of_birth",
        existing_type=sa.Date(),
        nullable=False,
    )

    op.alter_column(
        "borrowers",
        "district",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    # ---------------------------------------------------------
    # 3. Restore original borrower constraints
    # ---------------------------------------------------------

    op.drop_constraint(
        "fk_borrowers_user_id_users",
        "borrowers",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "borrowers_user_id_fkey",
        "borrowers",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_index(
        "ix_borrowers_user_id",
        table_name="borrowers",
    )

    op.create_unique_constraint(
        "borrowers_user_id_key",
        "borrowers",
        ["user_id"],
    )

    op.create_unique_constraint(
        "borrowers_passport_number_key",
        "borrowers",
        ["passport_number"],
    )

    op.create_unique_constraint(
        "borrowers_national_id_key",
        "borrowers",
        ["national_id"],
    )

    # ---------------------------------------------------------
    # 4. Restore nullable account columns
    # ---------------------------------------------------------

    op.alter_column(
        "users",
        "is_verified",
        existing_type=sa.Boolean(),
        nullable=True,
    )

    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=True,
    )

    op.alter_column(
        "refresh_tokens",
        "revoked",
        existing_type=sa.Boolean(),
        nullable=True,
    )

    op.alter_column(
        "borrowers",
        "consent_to_credit_checks",
        existing_type=sa.Boolean(),
        nullable=True,
    )

    op.alter_column(
        "borrowers",
        "consent_to_share_profile",
        existing_type=sa.Boolean(),
        nullable=True,
    )

    op.alter_column(
        "borrowers",
        "existing_loan_total",
        existing_type=sa.Numeric(
            precision=12,
            scale=2,
        ),
        nullable=True,
    )

    op.alter_column(
        "borrowers",
        "has_existing_loans",
        existing_type=sa.Boolean(),
        nullable=True,
    )

    # ---------------------------------------------------------
    # 5. Remove people table
    # ---------------------------------------------------------

    op.drop_index(
        "ix_people_passport_number",
        table_name="people",
    )

    op.drop_index(
        "ix_people_national_id",
        table_name="people",
    )

    op.drop_index(
        "ix_people_user_id",
        table_name="people",
    )

    op.drop_table("people")