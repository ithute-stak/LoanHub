"""add call management and recording quality assurance

Revision ID: c2r6t8u0v133
Revises: b1q5s7t9u022
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2r6t8u0v133"
down_revision: Union[str, Sequence[str], None] = "b1q5s7t9u022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "call_management_policies",
        *_base_columns(),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("recording_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recording_retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("call_metadata_retention_months", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("automatic_deletion_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("live_monitoring_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manager_downloads_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("legal_hold_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("recording_notice", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_call_management_policy_company"),
    )
    op.create_index("ix_call_management_policies_company_id", "call_management_policies", ["company_id"])

    op.create_table(
        "employee_call_devices",
        *_base_columns(),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("staff_id", sa.UUID(), nullable=False),
        sa.Column("device_uuid", sa.String(length=160), nullable=False),
        sa.Column("device_name", sa.String(length=180), nullable=True),
        sa.Column("platform", sa.String(length=40), nullable=False, server_default="android"),
        sa.Column("os_version", sa.String(length=80), nullable=True),
        sa.Column("app_version", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("registered_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["staff_id"], ["company_staff.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "device_uuid", name="uq_employee_call_device_company_uuid"),
    )
    op.create_index("ix_employee_call_devices_company_id", "employee_call_devices", ["company_id"])
    op.create_index("ix_employee_call_devices_branch_id", "employee_call_devices", ["branch_id"])
    op.create_index("ix_employee_call_devices_staff_id", "employee_call_devices", ["staff_id"])
    op.create_index("ix_employee_call_devices_device_uuid", "employee_call_devices", ["device_uuid"])
    op.create_index("ix_employee_call_devices_status", "employee_call_devices", ["status"])
    op.create_index("ix_employee_call_devices_last_seen_at", "employee_call_devices", ["last_seen_at"])

    op.create_table(
        "client_calls",
        *_base_columns(),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("employee_staff_id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=True),
        sa.Column("borrower_id", sa.UUID(), nullable=True),
        sa.Column("loan_id", sa.UUID(), nullable=True),
        sa.Column("device_call_uuid", sa.String(length=120), nullable=False),
        sa.Column("phone_number", sa.String(length=40), nullable=False),
        sa.Column("normalized_phone", sa.String(length=24), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="started"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recording_status", sa.String(length=30), nullable=False, server_default="not_requested"),
        sa.Column("outcome", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("media_room_name", sa.String(length=180), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_staff_id"], ["company_staff.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["device_id"], ["employee_call_devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "device_call_uuid", name="uq_client_call_company_device_uuid"),
        sa.UniqueConstraint("media_room_name", name="uq_client_calls_media_room_name"),
    )
    for name in (
        "company_id", "branch_id", "employee_staff_id", "device_id", "borrower_id", "loan_id",
        "device_call_uuid", "normalized_phone", "direction", "status", "started_at", "ended_at",
        "recording_status", "outcome", "media_room_name",
    ):
        op.create_index(f"ix_client_calls_{name}", "client_calls", [name])

    op.create_table(
        "call_recordings",
        *_base_columns(),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("call_id", sa.UUID(), nullable=False),
        sa.Column("managed_file_id", sa.UUID(), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("deletion_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["client_calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["managed_file_id"], ["managed_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id", name="uq_call_recording_call"),
        sa.UniqueConstraint("managed_file_id", name="uq_call_recording_managed_file"),
    )
    op.create_index("ix_call_recordings_company_id", "call_recordings", ["company_id"])
    op.create_index("ix_call_recordings_call_id", "call_recordings", ["call_id"])
    op.create_index("ix_call_recordings_managed_file_id", "call_recordings", ["managed_file_id"])
    op.create_index("ix_call_recordings_status", "call_recordings", ["status"])
    op.create_index("ix_call_recordings_deletion_at", "call_recordings", ["deletion_at"])

    op.create_table(
        "recording_legal_holds",
        *_base_columns(),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("recording_id", sa.UUID(), nullable=False),
        sa.Column("placed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("released_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("placed_at", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recording_id"], ["call_recordings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["placed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recording_legal_holds_company_id", "recording_legal_holds", ["company_id"])
    op.create_index("ix_recording_legal_holds_recording_id", "recording_legal_holds", ["recording_id"])
    op.create_index("ix_recording_legal_holds_placed_by_user_id", "recording_legal_holds", ["placed_by_user_id"])
    op.create_index("ix_recording_legal_holds_status", "recording_legal_holds", ["status"])

    op.create_table(
        "call_quality_reviews",
        *_base_columns(),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("call_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_user_id", sa.UUID(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("compliance_status", sa.String(length=40), nullable=False, server_default="not_assessed"),
        sa.Column("customer_care_status", sa.String(length=40), nullable=False, server_default="not_assessed"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["call_id"], ["client_calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "call_id", "reviewer_user_id",
            name="uq_call_quality_review_reviewer_call",
        ),
    )
    op.create_index("ix_call_quality_reviews_company_id", "call_quality_reviews", ["company_id"])
    op.create_index("ix_call_quality_reviews_branch_id", "call_quality_reviews", ["branch_id"])
    op.create_index("ix_call_quality_reviews_call_id", "call_quality_reviews", ["call_id"])
    op.create_index("ix_call_quality_reviews_reviewer_user_id", "call_quality_reviews", ["reviewer_user_id"])
    op.create_index("ix_call_quality_reviews_compliance_status", "call_quality_reviews", ["compliance_status"])
    op.create_index("ix_call_quality_reviews_customer_care_status", "call_quality_reviews", ["customer_care_status"])
    op.create_index("ix_call_quality_reviews_reviewed_at", "call_quality_reviews", ["reviewed_at"])


def downgrade() -> None:
    op.drop_table("call_quality_reviews")
    op.drop_table("recording_legal_holds")
    op.drop_table("call_recordings")
    op.drop_table("client_calls")
    op.drop_table("employee_call_devices")
    op.drop_table("call_management_policies")
