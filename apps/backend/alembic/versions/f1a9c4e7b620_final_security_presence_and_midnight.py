"""final security, presence and encrypted content alignment

Revision ID: f1a9c4e7b620
Revises: d4e7b6c1a930
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a9c4e7b620'
down_revision: Union[str, Sequence[str], None] = 'd4e7b6c1a930'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('SELECT pg_advisory_xact_lock(62106420260721)')
    op.execute("SET LOCAL lock_timeout = '60s'")
    op.execute("SET LOCAL statement_timeout = '20min'")

    op.add_column('users', sa.Column('last_seen_at', sa.DateTime(), nullable=True))
    op.create_index('ix_users_last_seen_at', 'users', ['last_seen_at'], unique=False)

    op.add_column('chat_messages', sa.Column('body_ciphertext', sa.Text(), nullable=True))
    op.add_column('chat_messages', sa.Column('body_nonce', sa.String(length=64), nullable=True))
    op.add_column('chat_messages', sa.Column('encryption_version', sa.String(length=20), nullable=True))

    op.add_column('managed_files', sa.Column('detected_mime_type', sa.String(length=150), nullable=True))
    op.add_column('managed_files', sa.Column('is_encrypted', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('managed_files', sa.Column('encryption_nonce', sa.String(length=64), nullable=True))
    op.add_column('managed_files', sa.Column('encryption_version', sa.String(length=20), nullable=True))
    op.add_column('managed_files', sa.Column('scan_status', sa.String(length=30), server_default='legacy', nullable=False))
    op.add_column('managed_files', sa.Column('quarantined_reason', sa.Text(), nullable=True))
    op.create_index('ix_managed_files_scan_status', 'managed_files', ['scan_status'], unique=False)

    op.execute("UPDATE managed_files SET detected_mime_type = mime_type WHERE detected_mime_type IS NULL")


def downgrade() -> None:
    op.drop_index('ix_managed_files_scan_status', table_name='managed_files')
    op.drop_column('managed_files', 'quarantined_reason')
    op.drop_column('managed_files', 'scan_status')
    op.drop_column('managed_files', 'encryption_version')
    op.drop_column('managed_files', 'encryption_nonce')
    op.drop_column('managed_files', 'is_encrypted')
    op.drop_column('managed_files', 'detected_mime_type')

    op.drop_column('chat_messages', 'encryption_version')
    op.drop_column('chat_messages', 'body_nonce')
    op.drop_column('chat_messages', 'body_ciphertext')

    op.drop_index('ix_users_last_seen_at', table_name='users')
    op.drop_column('users', 'last_seen_at')
