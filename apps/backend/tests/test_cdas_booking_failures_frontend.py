from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
MODEL = BACKEND / "database" / "models" / "cdas_booking.py"
MIGRATION = BACKEND / "alembic" / "versions" / "f6u0v2w4x029_cdas_booking_failures.py"
ROUTER = BACKEND / "routers" / "cdas_booking_failures.py"
PIPELINE_ROUTER = BACKEND / "routers" / "cdas_opportunity_pipeline.py"
API_ROUTER = BACKEND / "api" / "v1" / "router.py"
VIEW = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasBookingFailures.tsx"
PIPELINE_VIEW = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasOpportunityPipeline.tsx"
PAGE = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "failures" / "page.tsx"
LAYOUT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = FRONTEND / "api" / "cdasBooking.ts"


def test_failure_migration_is_additive_and_follows_contact_followups():
    model = MODEL.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "class CdasBookingFailure" in model
    assert 'down_revision = "e5t9u1v3w028"' in migration
    assert 'op.create_table(\n        "cdas_booking_failures"' in migration
    assert '"retry_eligible"' in migration
    assert '"retry_after"' in migration
    assert "DELETE FROM cdas" not in migration
    assert "DROP TABLE cdas_booking_opportunities" not in migration


def test_failure_api_is_company_scoped_and_retry_uses_latest_failure():
    source = ROUTER.read_text(encoding="utf-8")
    registry = API_ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/failures")' in source
    assert '@router.post("/opportunities/{opportunity_id}/failures")' in source
    assert '@router.get("/opportunities/{opportunity_id}/failures")' in source
    assert '@router.post("/opportunities/{opportunity_id}/retry-failed")' in source
    assert "CdasBookingOpportunity.company_id == context.company_id" in source
    assert "CdasBookingFailure.company_id == context.company_id" in source
    assert "created_by_user_id=context.user.id" in source
    assert "reopen_failed_opportunity" in source
    assert "cdas_booking_failures.router" in registry


def test_pipeline_cannot_move_directly_to_failed_without_a_reason():
    router = PIPELINE_ROUTER.read_text(encoding="utf-8")
    view = PIPELINE_VIEW.read_text(encoding="utf-8")

    assert 'str(payload.stage or "").strip().lower() == "failed"' in router
    assert "Record the booking failure reason in Failure Tracking" in router
    assert '{ id: "failed", label: "Failed" }' not in view
    assert "/company/cdas-booking/failures" in view


def test_failure_tracking_frontend_exposes_record_retry_history_and_reason_counts():
    view = VIEW.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    for label in ("CDAS Booking Failure Tracking", "Record a failed booking", "Failure history", "Retry due now", "Allow this opportunity to be retried", "Reopen for retry"):
        assert label in view
    assert "reason_counts" in view
    assert "CdasBookingFailuresView" in page
    assert "/company/cdas-booking/failures" in layout
    assert '"/cdas-booking/failures"' in api
    assert "recordBookingFailure" in api
    assert "retryFailedBooking" in api
