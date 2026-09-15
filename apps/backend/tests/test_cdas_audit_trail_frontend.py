from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_formal_audit_endpoint_is_company_scoped_read_only_and_role_protected() -> None:
    router = _read(BACKEND / "routers" / "cdas_audit_trail.py")
    api_router = _read(BACKEND / "api" / "v1" / "router.py")

    assert '@router.get("/audit-trail")' in router
    assert "TRANSPARENCY_ROLES" in router
    assert "AuditLog.company_id == context.company_id" in router
    assert "Unsupported CDAS audit action" in router
    assert "Audit start date cannot be after end date" in router
    assert "cdas_audit_trail.router" in api_router
    assert '@router.post("/audit-trail")' not in router
    assert '@router.patch("/audit-trail")' not in router
    assert '@router.delete("/audit-trail")' not in router


def test_cdas_audit_events_are_hash_sealed_and_append_only() -> None:
    service = _read(BACKEND / "services" / "cdas_audit_trail.py")
    integrity = _read(BACKEND / "core" / "audit_integrity.py")

    assert '@event.listens_for(Session, "before_flush")' in service
    assert '@event.listens_for(Session, "after_flush_postexec")' in service
    assert "session.add(event_row)" in service
    assert '"formal_cdas_audit": True' in service
    assert "analysis_snapshot" in service
    assert "reason_details" in service
    assert "notes" in service
    assert 'raise ValueError("Sealed audit events are immutable")' in integrity
    assert "item.event_hash = audit_hash(item, previous)" in integrity
    assert 'item.hash_version = "sha256-v1"' in integrity


def test_bulk_processing_adds_safe_batch_summary_audit_event() -> None:
    router = _read(BACKEND / "routers" / "cdas_bulk_processing.py")

    assert "append_cdas_audit_event" in router
    assert 'action="CDAS_BULK_ANALYSIS_COMPLETED"' in router
    assert '"analysis_ids": analysis_ids' in router
    assert '"input_count": len(payload.items)' in router
    audit_block = router.split('action="CDAS_BULK_ANALYSIS_COMPLETED"', 1)[1]
    assert "raw_text" not in audit_block


def test_frontend_audit_api_route_navigation_and_workspace_are_wired() -> None:
    api = _read(FRONTEND / "api" / "cdasBooking.ts")
    layout = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx")
    page = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "audit-trail" / "page.tsx")
    component = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "CdasAuditTrail.tsx")

    assert '"/cdas-booking/audit-trail"' in api
    assert "CdasAuditTrailParams" in api
    assert "CdasAuditTrailResponse" in api
    assert 'href="/company/cdas-booking/audit-trail"' in layout
    assert "Audit Trail" in layout
    assert "CdasAuditTrail" in page

    for phrase in (
        "Formal CDAS Audit Trail",
        "Read-only integrity record",
        "Raw pasted CDAS text",
        "Hash version",
        "Event hash",
        "SEALED",
        "UNSEALED",
        "transparency role",
    ):
        assert phrase in component

    assert "cdasBookingApi.getAuditTrail" in component
    assert "cdasBookingApi.delete" not in component
    assert "cdasBookingApi.updateAudit" not in component


def test_audit_frontend_types_expose_integrity_without_raw_cdas_source() -> None:
    types = _read(FRONTEND / "types" / "cdasAuditTrail.ts")

    assert "previous_hash" in types
    assert "event_hash" in types
    assert "sealed_at" in types
    assert "before_data" in types
    assert "after_data" in types
    assert "raw_text" not in types
