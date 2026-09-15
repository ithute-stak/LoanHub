from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
MODEL = BACKEND / "database" / "models" / "cdas_booking.py"
MIGRATION = BACKEND / "alembic" / "versions" / "e5t9u1v3w028_cdas_contact_followups.py"
ROUTER = BACKEND / "routers" / "cdas_contact_followups.py"
API_ROUTER = BACKEND / "api" / "v1" / "router.py"
VIEW = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasContactFollowUps.tsx"
PAGE = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "follow-ups" / "page.tsx"
LAYOUT = FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx"
API = FRONTEND / "api" / "cdasBooking.ts"


def test_follow_up_migration_adds_assignment_and_append_only_contact_table():
    model = MODEL.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "assigned_to_user_id = Column(UUID" in model
    assert "class CdasOpportunityContact" in model
    assert 'down_revision = "d4s8t0u2v027"' in migration
    assert 'op.create_table(\n        "cdas_opportunity_contacts"' in migration
    assert 'op.add_column(\n        "cdas_booking_opportunities"' in migration
    assert "op.drop_table" in migration  # downgrade only
    assert "DELETE FROM cdas" not in migration
    assert "DROP TABLE cdas_booking_opportunities" not in migration


def test_follow_up_api_is_company_scoped_and_assignment_requires_active_company_staff():
    source = ROUTER.read_text(encoding="utf-8")
    registry = API_ROUTER.read_text(encoding="utf-8")

    assert '@router.get("/follow-ups")' in source
    assert '@router.post("/opportunities/{opportunity_id}/contacts")' in source
    assert '@router.patch("/opportunities/{opportunity_id}/assignment")' in source
    assert "CdasBookingOpportunity.company_id == context.company_id" in source
    assert "CdasOpportunityContact.company_id == context.company_id" in source
    assert "CompanyStaff.company_id == context.company_id" in source
    assert "CompanyStaff.is_active.is_(True)" in source
    assert "created_by_user_id=context.user.id" in source
    assert "cdas_contact_followups.router" in registry


def test_frontend_exposes_contact_channels_outcomes_assignment_and_history():
    view = VIEW.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    layout = LAYOUT.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    for label in ("Call", "WhatsApp", "SMS", "Email", "No Answer", "Interested", "Not Interested", "Call Back / Return Later", "Documents Requested", "Documents Received", "Submitted"):
        assert label in view
    assert "Assigned officer" in view
    assert "Next follow-up" in view
    assert "Contact history" in view
    assert "CdasContactFollowUpsView" in page
    assert "/company/cdas-booking/follow-ups" in layout
    assert '"/cdas-booking/follow-ups"' in api
    assert "addContact" in api
    assert "assignOpportunity" in api
