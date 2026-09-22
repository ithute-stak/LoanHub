"""Enforce CDAS API username tenant isolation

Revision ID: e8w2x4y6z249
Revises: d7v1w3x5y248
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e8w2x4y6z249"
down_revision: Union[str, Sequence[str], None] = "d7v1w3x5y248"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_origination_cdas_environment_username"


def upgrade() -> None:
    # CDAS applies its quota and provider-side ownership to the API username.
    # One normalized username/environment pair must therefore belong to exactly
    # one LoanHub company. The expression index closes races between concurrent
    # settings requests that cannot be eliminated by an application-level check.
    op.execute(
        f"""
        CREATE UNIQUE INDEX {INDEX_NAME}
        ON origination_integration_configurations (
            environment,
            lower(btrim(configuration ->> 'username'))
        )
        WHERE provider = 'cdas'
          AND coalesce(btrim(configuration ->> 'username'), '') <> ''
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
