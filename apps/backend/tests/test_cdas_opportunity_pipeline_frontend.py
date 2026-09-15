from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
MODEL = BACKEND / "database" / "models" / "cdas_booking.py"
MIGRATION = BACKEND / "alembic" / "versions" / "d4s8t0u2v027_cdas_opportunity_pipeline.py"
MONITOR = BACKEND / "services" / "cdas_booking_monitor.py"
PIPELINE_ROUTER = BACKEND / "routers" / "cdas_opportunity_pipeline.py"
CALENDAR_ROUTER = BACKEND / "routers" / "cdas_booking_calendar.py"
API_ROUTER = BACKEND / "api" / "v1" / "router.py"
VIEW = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasOpportunityPipeline.tsx"
PAGE = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "pipeline" / "page.tsx"
LAYOUT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = FRONTEND / "api" / "cdasBooking.ts"
TYPES = FRONTEND / "types" / "cdasBooking.ts"


def test_pipeline_migration_is_additive_and_backfills_existing_opportunities():
    model = MODEL.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    assert 'pipeline_stage = Column(String(40)' in model
    assert 'pipeline_updated_at = Column(DateTime' in model
    assert 'pipeline_updated_by_user_id = Column(UUID' in model
    assert 'down_revision = "c3r7t9u1v026"' in migration
    assert 'WHEN status = \'booked\' THEN \'booked\'' in migration
    assert "ELSE 'identified'" in migration
    assert "op.drop_column" in migration
    assert "op.drop_table" not in migration


def test_pipeline_api_is_tenant_scoped_and_registered():
    router = PIPELINE_ROUTER.read_text(encoding="utf-8")
    registry = API_ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/pipeline")' in router
    assert '@router.patch("/opportunities/{opportunity_id}/pipeline")' in router
    assert "CdasBookingOpportunity.company_id == context.company_id" in router
    assert "_require_company_member(context)" in router
    assert "cdas_opportunity_pipeline" in registry
    assert "cdas_opportunity_pipeline.router" in registry


def test_failed_pipeline_records_stop_active_reminders_and_priority_calendar_work():
    monitor = MONITOR.read_text(encoding="utf-8")
    calendar_router = CALENDAR_ROUTER.read_text(encoding="utf-8")

    assert 'CdasBookingOpportunity.pipeline_stage.notin_(["failed", "booked"])' in monitor
    assert 'CdasBookingOpportunity.pipeline_stage != "failed"' in calendar_router
    assert 'return "FAILED"' in monitor


def test_frontend_exposes_all_pipeline_stages_and_persists_updates():
    source = VIEW.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    types = TYPES.read_text(encoding="utf-8")

    for label in (
        "Identified",
        "Contact Client",
        "Documents Required",
        "Ready to Book",
        "Booking Submitted",
        "Approved",
        "Failed",
        "Booked",
    ):
        assert label in source

    assert "CdasOpportunityPipelineView" in page
    assert "/company/cdas-booking/pipeline" in layout
    assert '"/cdas-booking/pipeline"' in api
    assert "updatePipelineStage" in api
    assert '{ stage: "booked" }' in api
    assert 'CdasPipelineStage = "identified"' in types
    assert 'CdasOpportunityState = "UPCOMING" | "BOOK_NOW" | "FAILED" | "BOOKED"' in types
