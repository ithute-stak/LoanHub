"""Staged transactional Data Center event journal, capture OFF by default.

Revision ID: dc20261122001
Revises: a9b0c1d2e346

A per-company cursor row serializes change events in commit order. Triggered
writes share the originating transaction and roll back with it. All event
payloads are metadata-only (no balances, identities, contact or payment data).
Capture requires an explicit administrative opt-in per company after tests.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "dc20261122001"
down_revision = "a9b0c1d2e346"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loanhub_dc_capture",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "loanhub_dc_clock",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cursor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint("cursor >= 0", name="ck_loanhub_dc_clock_nonnegative"),
    )
    op.create_table(
        "loanhub_dc_event",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cursor", sa.BigInteger(), nullable=False),
        sa.Column("resource", sa.String(40), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(12), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.PrimaryKeyConstraint("company_id", "cursor", name="pk_loanhub_dc_event"),
        sa.CheckConstraint("cursor > 0", name="ck_loanhub_dc_event_positive_cursor"),
        sa.CheckConstraint("action IN ('created', 'updated', 'deleted')", name="ck_loanhub_dc_event_action"),
        sa.CheckConstraint("resource IN ('branches', 'loanProducts', 'staff', 'clients', 'loans', 'payments')",
                           name="ck_loanhub_dc_event_resource"),
    )
    # The app may read event/cursor rows only for its bound tenant. The
    # capture toggle cannot be written by a normal application connection.
    for table in ("loanhub_dc_capture", "loanhub_dc_clock", "loanhub_dc_event"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    for table in ("loanhub_dc_clock", "loanhub_dc_event"):
        op.execute(f"""
            CREATE POLICY loanhub_dc_tenant_read ON public.{table}
            FOR SELECT USING (
                company_id::text = current_setting('loanhub.company_id', true)
                AND current_setting('loanhub.actor_scope', true) = 'tenant'
            )
        """)

    op.execute("""
        CREATE FUNCTION public.loanhub_dc_append_change(
            target_company uuid, resource_name text, target_entity uuid,
            target_branch uuid, change_action text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $body$
        DECLARE
            next_cursor bigint;
        BEGIN
            IF target_company IS NULL OR target_entity IS NULL THEN RETURN; END IF;
            -- No company is enabled by this migration. Only a trusted operator
            -- may add a capture row after the end-to-end gates pass.
            IF NOT EXISTS (
                SELECT 1 FROM public.loanhub_dc_capture
                WHERE company_id = target_company AND enabled IS TRUE
            ) THEN RETURN; END IF;

            -- Company row lock persists to COMMIT. Other transactions writing
            -- this company wait, so committed cursors cannot overtake.
            INSERT INTO public.loanhub_dc_clock AS company_clock (company_id, cursor)
            VALUES (target_company, 1)
            ON CONFLICT (company_id) DO UPDATE SET cursor = company_clock.cursor + 1
            RETURNING cursor INTO next_cursor;

            INSERT INTO public.loanhub_dc_event (
                company_id, cursor, resource, entity_id, branch_id, action
            ) VALUES (
                target_company, next_cursor, resource_name, target_entity,
                target_branch, change_action
            );
        END;
        $body$
    """)

    op.execute("""
        CREATE FUNCTION public.loanhub_dc_capture_change() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $body$
        DECLARE
            kind text;
            previous_branch uuid;
            next_branch uuid;
        BEGIN
            kind := CASE TG_TABLE_NAME
                WHEN 'company_branches' THEN 'branches'
                WHEN 'loan_products' THEN 'loanProducts'
                WHEN 'company_staff' THEN 'staff'
                WHEN 'company_borrower_accounts' THEN 'clients'
                WHEN 'client_company_loan' THEN 'loans'
                WHEN 'payment_transactions' THEN 'payments'
                ELSE NULL END;
            IF kind IS NULL THEN
                RAISE EXCEPTION 'Unsupported Data Center change table %', TG_TABLE_NAME;
            END IF;
            -- Fast exit: when no involved company opted in, never inspect
            -- the actual row (which may contain encrypted financial fields).
            IF TG_OP = 'INSERT' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM public.loanhub_dc_capture
                    WHERE company_id = NEW.company_id AND enabled IS TRUE
                ) THEN RETURN NEW; END IF;
            ELSIF TG_OP = 'DELETE' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM public.loanhub_dc_capture
                    WHERE company_id = OLD.company_id AND enabled IS TRUE
                ) THEN RETURN OLD; END IF;
            ELSE
                IF NOT EXISTS (
                    SELECT 1 FROM public.loanhub_dc_capture
                    WHERE company_id IN (OLD.company_id, NEW.company_id)
                    AND enabled IS TRUE
                ) THEN RETURN NEW; END IF;
            END IF;
            IF TG_OP IN ('UPDATE', 'DELETE') THEN
                previous_branch := NULLIF(to_jsonb(OLD)->>'branch_id', '')::uuid;
            END IF;
            IF TG_OP IN ('UPDATE', 'INSERT') THEN
                next_branch := NULLIF(to_jsonb(NEW)->>'branch_id', '')::uuid;
            END IF;

            IF TG_OP = 'DELETE' THEN
                PERFORM public.loanhub_dc_append_change(
                    OLD.company_id, kind, OLD.id, previous_branch, 'deleted'
                );
                RETURN OLD;
            ELSIF TG_OP = 'INSERT' THEN
                PERFORM public.loanhub_dc_append_change(
                    NEW.company_id, kind, NEW.id, next_branch, 'created'
                );
            ELSE
                IF OLD.company_id IS DISTINCT FROM NEW.company_id THEN
                    PERFORM public.loanhub_dc_append_change(
                        OLD.company_id, kind, OLD.id, previous_branch, 'deleted'
                    );
                    PERFORM public.loanhub_dc_append_change(
                        NEW.company_id, kind, NEW.id, next_branch, 'created'
                    );
                ELSE
                    PERFORM public.loanhub_dc_append_change(
                        NEW.company_id, kind, NEW.id, next_branch, 'updated'
                    );
                END IF;
            END IF;
            RETURN NEW;
        END;
        $body$
    """)
    for table in (
        "company_branches", "loan_products", "company_staff",
        "company_borrower_accounts", "client_company_loan", "payment_transactions",
    ):
        op.execute(f"""
            CREATE TRIGGER loanhub_dc_change_capture
            AFTER INSERT OR UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.loanhub_dc_capture_change()
        """)
    op.execute("""
        REVOKE ALL ON FUNCTION public.loanhub_dc_append_change(
            uuid, text, uuid, uuid, text
        ) FROM PUBLIC
    """)
    op.execute("REVOKE ALL ON FUNCTION public.loanhub_dc_capture_change() FROM PUBLIC")
    op.execute("""
        DO $body$
        BEGIN
            IF to_regrole('loanhub_app') IS NOT NULL THEN
                REVOKE ALL ON TABLE public.loanhub_dc_capture,
                    public.loanhub_dc_clock, public.loanhub_dc_event FROM loanhub_app;
                GRANT SELECT ON TABLE public.loanhub_dc_clock,
                    public.loanhub_dc_event TO loanhub_app;
            END IF;
        END;
        $body$
    """)


def downgrade():
    for table in (
        "payment_transactions", "client_company_loan",
        "company_borrower_accounts", "company_staff",
        "loan_products", "company_branches",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS loanhub_dc_change_capture ON public.{table}")
    op.execute("DROP FUNCTION IF EXISTS public.loanhub_dc_capture_change()")
    op.execute("DROP FUNCTION IF EXISTS public.loanhub_dc_append_change(uuid, text, uuid, uuid, text)")
    op.drop_table("loanhub_dc_event")
    op.drop_table("loanhub_dc_clock")
    op.drop_table("loanhub_dc_capture")
