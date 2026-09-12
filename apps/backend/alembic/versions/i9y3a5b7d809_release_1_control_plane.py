"""Add LoanHub release-one security and governance controls.

Revision ID: i9y3a5b7d809
Revises: h8x2z4a6c798
"""

import hashlib
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "i9y3a5b7d809"
down_revision = "h8x2z4a6c798"
branch_labels = None
depends_on = None


def _base_columns():
    return (
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def _seal_existing_audit_rows() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("""
        SELECT id, user_id, company_id, branch_id, action, table_name,
               entity_type, record_id, description, actor_role, severity,
               status, before_data, after_data, changed_fields, event_data,
               request_id, created_at
        FROM audit_logs
        ORDER BY created_at, id
    """)).mappings().all()
    previous = "0" * 64
    for row in rows:
        payload = {
            "action": row["action"],
            "actor_role": row["actor_role"],
            "after_data": row["after_data"] or {},
            "before_data": row["before_data"] or {},
            "branch_id": str(row["branch_id"]) if row["branch_id"] else None,
            "changed_fields": row["changed_fields"] or [],
            "company_id": str(row["company_id"]) if row["company_id"] else None,
            "description": row["description"],
            "entity_type": row["entity_type"],
            "event_data": row["event_data"] or {},
            "previous_hash": previous,
            "record_id": str(row["record_id"]) if row["record_id"] else None,
            "request_id": row["request_id"],
            "severity": row["severity"],
            "status": row["status"],
            "table_name": row["table_name"],
            "user_id": str(row["user_id"]) if row["user_id"] else None,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        event_hash = hashlib.sha256(canonical).hexdigest()
        connection.execute(
            sa.text("""
                UPDATE audit_logs
                SET previous_hash = :previous_hash,
                    event_hash = :event_hash,
                    hash_version = 'sha256-v1',
                    sealed_at = created_at
                WHERE id = :id
            """),
            {"id": row["id"], "previous_hash": previous, "event_hash": event_hash},
        )
        previous = event_hash


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("previous_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("event_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("hash_version", sa.String(length=30), nullable=True))
    op.add_column("audit_logs", sa.Column("sealed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_audit_logs_previous_hash", "audit_logs", ["previous_hash"])
    op.create_index("ix_audit_logs_event_hash", "audit_logs", ["event_hash"], unique=True)
    _seal_existing_audit_rows()

    op.add_column("refresh_tokens", sa.Column("session_version", sa.String(length=20), server_default="1", nullable=False))
    op.add_column("refresh_tokens", sa.Column("device_name", sa.String(length=160), nullable=True))
    op.add_column("refresh_tokens", sa.Column("ip_hash", sa.String(length=64), nullable=True))
    op.add_column("refresh_tokens", sa.Column("user_agent", sa.String(length=500), nullable=True))
    op.add_column("refresh_tokens", sa.Column("last_used_at", sa.DateTime(), nullable=True))

    op.add_column("company_webhook_endpoints", sa.Column("encrypted_secret", sa.Text(), nullable=True))
    op.add_column("company_webhook_endpoints", sa.Column("encryption_nonce", sa.String(length=80), nullable=True))
    op.add_column("company_webhook_endpoints", sa.Column("encryption_version", sa.String(length=30), nullable=True))

    op.create_table(
        "user_mfa_enrollments",
        *_base_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("encryption_nonce", sa.String(length=80), nullable=False),
        sa.Column("encryption_version", sa.String(length=30), nullable=False),
        sa.Column("recovery_code_hashes", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("last_accepted_counter", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_mfa_user"),
    )
    op.create_index("ix_user_mfa_enrollments_user_id", "user_mfa_enrollments", ["user_id"])
    op.create_index("ix_user_mfa_enrollments_is_enabled", "user_mfa_enrollments", ["is_enabled"])

    op.create_table(
        "user_security_states",
        *_base_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_failed_login_at", sa.DateTime(), nullable=True),
        sa.Column("last_successful_login_at", sa.DateTime(), nullable=True),
        sa.Column("session_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_security_state_user"),
    )
    op.create_index("ix_user_security_states_user_id", "user_security_states", ["user_id"])
    op.create_index("ix_user_security_states_locked_until", "user_security_states", ["locked_until"])

    op.create_table(
        "approval_requests",
        *_base_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_approval_company_idempotency"),
    )
    for name in ("company_id", "branch_id", "action_type", "resource_type", "resource_id", "status"):
        op.create_index(f"ix_approval_requests_{name}", "approval_requests", [name])

    op.create_table(
        "payment_adjustments",
        *_base_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("adjustment_type", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="LSL", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending_approval", nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_reference", sa.String(length=180), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payment_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_payment_adjustment_company_idempotency"),
    )
    for name in ("company_id", "payment_id", "approval_request_id", "adjustment_type", "status", "provider_reference"):
        op.create_index(f"ix_payment_adjustments_{name}", "payment_adjustments", [name])

    op.create_table(
        "webhook_outbox_events",
        *_base_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=80), nullable=True),
        sa.Column("aggregate_id", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["company_webhook_endpoints.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("endpoint_id", "idempotency_key", name="uq_webhook_outbox_endpoint_idempotency"),
    )
    for name in ("company_id", "endpoint_id", "event_type", "aggregate_id", "status", "next_attempt_at"):
        op.create_index(f"ix_webhook_outbox_events_{name}", "webhook_outbox_events", [name])

    op.create_table(
        "webhook_delivery_attempts",
        *_base_columns(),
        sa.Column("outbox_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("request_timestamp", sa.DateTime(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body_hash", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["outbox_event_id"], ["webhook_outbox_events.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_webhook_delivery_attempts_outbox_event_id", "webhook_delivery_attempts", ["outbox_event_id"])

    op.create_table(
        "accounting_periods",
        *_base_columns(),
        sa.Column("scope_key", sa.String(length=80), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("locked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("close_note", sa.Text(), nullable=True),
        sa.CheckConstraint("period_end >= period_start", name="ck_accounting_period_order"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["locked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("scope_key", "period_start", "period_end", name="uq_accounting_scope_period"),
    )
    for name in ("scope_key", "company_id", "branch_id", "period_start", "period_end", "status"):
        op.create_index(f"ix_accounting_periods_{name}", "accounting_periods", [name])

    op.create_table(
        "bank_statement_lines",
        *_base_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_reference", sa.String(length=180), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("reference", sa.String(length=180), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="LSL", nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="unmatched", nullable=False),
        sa.Column("matched_payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["branch_id"], ["company_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_payment_id"], ["payment_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("company_id", "source_fingerprint", name="uq_bank_line_company_fingerprint"),
    )
    for name in ("company_id", "branch_id", "account_reference", "transaction_date", "reference", "status", "matched_payment_id"):
        op.create_index(f"ix_bank_statement_lines_{name}", "bank_statement_lines", [name])

    op.create_table(
        "loan_guarantors",
        *_base_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guarantor_borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.String(length=240), nullable=False),
        sa.Column("national_id", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("relationship_to_borrower", sa.String(length=100), nullable=False),
        sa.Column("guaranteed_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("consent_obtained", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("verification_status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("verified_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guarantor_borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for name in ("company_id", "loan_id", "guarantor_borrower_id", "national_id", "verification_status"):
        op.create_index(f"ix_loan_guarantors_{name}", "loan_guarantors", [name])

    op.create_table(
        "loan_collateral",
        *_base_columns(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collateral_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ownership_reference", sa.String(length=180), nullable=True),
        sa.Column("estimated_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("forced_sale_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="LSL", nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="proposed", nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("forced_sale_value IS NULL OR forced_sale_value <= estimated_value", name="ck_collateral_forced_sale_value"),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="CASCADE"),
    )
    for name in ("company_id", "loan_id", "collateral_type", "ownership_reference", "status"):
        op.create_index(f"ix_loan_collateral_{name}", "loan_collateral", [name])

    op.create_table(
        "complaint_cases",
        *_base_columns(),
        sa.Column("reference", sa.String(length=80), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("subject", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="normal", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["loan_companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["loan_id"], ["client_company_loan.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reference", name="uq_complaint_reference"),
    )
    for name in ("reference", "company_id", "borrower_id", "loan_id", "category", "priority", "status", "due_at"):
        op.create_index(f"ix_complaint_cases_{name}", "complaint_cases", [name])

    op.create_table(
        "data_rights_requests",
        *_base_columns(),
        sa.Column("reference", sa.String(length=80), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="received", nullable=False),
        sa.Column("identity_verified_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["borrower_id"], ["borrowers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reference", name="uq_data_rights_reference"),
    )
    for name in ("reference", "user_id", "borrower_id", "request_type", "status", "due_at"):
        op.create_index(f"ix_data_rights_requests_{name}", "data_rights_requests", [name])


def downgrade() -> None:
    for table in (
        "data_rights_requests",
        "complaint_cases",
        "loan_collateral",
        "loan_guarantors",
        "bank_statement_lines",
        "accounting_periods",
        "webhook_delivery_attempts",
        "webhook_outbox_events",
        "payment_adjustments",
        "approval_requests",
        "user_security_states",
        "user_mfa_enrollments",
    ):
        op.drop_table(table)

    op.drop_column("company_webhook_endpoints", "encryption_version")
    op.drop_column("company_webhook_endpoints", "encryption_nonce")
    op.drop_column("company_webhook_endpoints", "encrypted_secret")
    for column in ("last_used_at", "user_agent", "ip_hash", "device_name", "session_version"):
        op.drop_column("refresh_tokens", column)
    op.drop_index("ix_audit_logs_event_hash", table_name="audit_logs")
    op.drop_index("ix_audit_logs_previous_hash", table_name="audit_logs")
    op.drop_column("audit_logs", "sealed_at")
    op.drop_column("audit_logs", "hash_version")
    op.drop_column("audit_logs", "event_hash")
    op.drop_column("audit_logs", "previous_hash")
