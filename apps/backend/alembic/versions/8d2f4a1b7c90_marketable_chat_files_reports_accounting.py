"""marketable chat, files, reports and accounting

Revision ID: 8d2f4a1b7c90
Revises: 3957062b7c66
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8d2f4a1b7c90"
down_revision: Union[str, Sequence[str], None] = "3957062b7c66"
branch_labels = None
depends_on = None


def base_columns():
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    # Only one LoanHub schema migration may run at a time. Application and
    # maintenance workers should still be stopped before applying this revision.
    op.get_bind().execute(
        sa.text("SELECT pg_advisory_xact_lock(62106420260716)")
    )
    op.get_bind().execute(sa.text("SET LOCAL lock_timeout = '60s'"))
    op.get_bind().execute(sa.text("SET LOCAL statement_timeout = '20min'"))

    op.create_table(
        "managed_files",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=700), nullable=False),
        sa.Column("storage_provider", sa.String(length=30), nullable=False),
        sa.Column("mime_type", sa.String(length=150), nullable=False),
        sa.Column("extension", sa.String(length=30), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("visibility", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("linked_entity_type", sa.String(length=100), nullable=True),
        sa.Column("linked_entity_id", sa.String(length=120), nullable=True),
        sa.Column("is_confidential", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reference"),
        sa.UniqueConstraint("storage_key"),
    )
    for column in ("owner_user_id", "company_id", "branch_id", "reference", "checksum_sha256", "category", "visibility", "linked_entity_type", "linked_entity_id", "is_deleted"):
        op.create_index(f"ix_managed_files_{column}", "managed_files", [column])

    op.create_table(
        "chat_conversations",
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("conversation_type", sa.String(length=40), nullable=False),
        sa.Column("context_type", sa.String(length=80), nullable=True),
        sa.Column("context_id", sa.String(length=120), nullable=True),
        sa.Column("is_group", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reference"),
    )
    for column in ("reference", "company_id", "branch_id", "created_by_user_id", "conversation_type", "context_type", "context_id", "is_archived", "last_message_at"):
        op.create_index(f"ix_chat_conversations_{column}", "chat_conversations", [column])

    op.create_table(
        "chat_participants",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_role", sa.String(length=80), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(), nullable=True),
        sa.Column("muted_until", sa.DateTime(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_chat_participant_conversation_user"),
    )
    op.create_index("ix_chat_participants_conversation_id", "chat_participants", ["conversation_id"])
    op.create_index("ix_chat_participants_user_id", "chat_participants", ["user_id"])
    op.create_index("ix_chat_participants_is_active", "chat_participants", ["is_active"])

    op.create_table(
        "chat_messages",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reply_to_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("client_message_id", sa.String(length=100), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reply_to_message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("sender_user_id", "client_message_id", name="uq_chat_message_sender_client_id"),
    )
    for column in ("conversation_id", "sender_user_id", "company_id", "branch_id", "message_type", "deleted_at"):
        op.create_index(f"ix_chat_messages_{column}", "chat_messages", [column])

    op.create_table(
        "chat_message_attachments",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("caption", sa.String(length=500), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["managed_files.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("message_id", "file_id", name="uq_chat_message_file"),
    )
    op.create_index("ix_chat_message_attachments_message_id", "chat_message_attachments", ["message_id"])
    op.create_index("ix_chat_message_attachments_file_id", "chat_message_attachments", ["file_id"])

    op.create_table(
        "accounting_accounts",
        sa.Column("scope_key", sa.String(length=80), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("account_type", sa.String(length=30), nullable=False),
        sa.Column("normal_balance", sa.String(length=10), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *base_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_id"], ["accounting_accounts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("scope_key", "code", name="uq_accounting_scope_code"),
    )
    for column in ("scope_key", "scope_type", "company_id", "branch_id", "account_type", "is_active"):
        op.create_index(f"ix_accounting_accounts_{column}", "accounting_accounts", [column])

    op.create_table(
        "journal_entries",
        sa.Column("scope_key", sa.String(length=80), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("posted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entry_number", sa.String(length=60), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_type", sa.String(length=80), nullable=True),
        sa.Column("reference_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_debit", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_credit", sa.Numeric(18, 2), nullable=False),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["posted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("scope_key", "entry_number", name="uq_journal_scope_number"),
        sa.UniqueConstraint("scope_key", "reference_type", "reference_id", name="uq_journal_scope_reference"),
    )
    for column in ("scope_key", "scope_type", "company_id", "branch_id", "entry_number", "entry_date", "reference_type", "reference_id", "status"):
        op.create_index(f"ix_journal_entries_{column}", "journal_entries", [column])

    op.create_table(
        "journal_lines",
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False),
        *base_columns(),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounting_accounts.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_journal_lines_journal_entry_id", "journal_lines", ["journal_entry_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])

    op.create_table(
        "report_schedules",
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("report_type", sa.String(length=50), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("output_format", sa.String(length=10), nullable=False),
        sa.Column("recipients", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=30), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *base_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in ("scope_type", "company_id", "branch_id", "report_type", "frequency", "is_active", "next_run_at"):
        op.create_index(f"ix_report_schedules_{column}", "report_schedules", [column])

    op.create_table(
        "generated_reports",
        sa.Column("reference", sa.String(length=50), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("report_type", sa.String(length=50), nullable=False),
        sa.Column("output_format", sa.String(length=10), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        *base_columns(),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["schedule_id"], ["report_schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_id"], ["managed_files.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reference"),
    )
    for column in ("reference", "scope_type", "company_id", "branch_id", "schedule_id", "report_type", "status"):
        op.create_index(f"ix_generated_reports_{column}", "generated_reports", [column])


def downgrade() -> None:
    for table in [
        "generated_reports",
        "report_schedules",
        "journal_lines",
        "journal_entries",
        "accounting_accounts",
        "chat_message_attachments",
        "chat_messages",
        "chat_participants",
        "chat_conversations",
        "managed_files",
    ]:
        op.drop_table(table)
