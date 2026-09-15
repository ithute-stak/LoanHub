from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_duplicate_detection_route_api_and_navigation_are_wired() -> None:
    api = _read(FRONTEND / "api" / "cdasBooking.ts")
    layout = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "layout.tsx")
    page = _read(FRONTEND / "app" / "(dashboard)" / "company" / "cdas-booking" / "duplicates" / "page.tsx")
    router = _read(BACKEND / "routers" / "cdas_duplicate_detection.py")
    registry = _read(BACKEND / "api" / "v1" / "router.py")

    assert '"/cdas-booking/duplicates"' in api
    assert 'href="/company/cdas-booking/duplicates"' in layout
    assert "Duplicate Detection" in layout
    assert "CdasDuplicateDetectionView" in page
    assert '@router.get("/duplicates")' in router
    assert "_require_company_member(context)" in router
    assert "CdasAnalysisRecord.company_id == context.company_id" in router
    assert "CdasBookingOpportunity.company_id == context.company_id" in router
    assert "cdas_duplicate_detection.router" in registry


def test_duplicate_detection_ui_is_review_only_and_explainable() -> None:
    component = _read(
        FRONTEND
        / "app"
        / "(dashboard)"
        / "company"
        / "cdas-booking"
        / "CdasDuplicateDetection.tsx"
    )

    for phrase in (
        "CDAS Client Duplicate Detection",
        "Possible duplicate client profiles",
        "Exact shared identifiers",
        "High confidence",
        "Medium confidence",
        "Affected profiles",
        "Review only",
        "No fuzzy name matching",
        "no automatic profile merging",
    ):
        assert phrase in component

    assert "mergeClient" not in component
    assert "autoMerge" not in component


def test_duplicate_detection_contract_exposes_review_identity_but_no_mutation_api() -> None:
    types = _read(FRONTEND / "types" / "cdasDuplicateDetection.ts")
    api = _read(FRONTEND / "api" / "cdasBooking.ts")
    service = _read(BACKEND / "services" / "cdas_duplicate_detection.py")
    router = _read(BACKEND / "routers" / "cdas_duplicate_detection.py")

    for field in ("client_name", "client_reference", "employee_no", "nid", "employer"):
        assert field in types

    assert "automatic_merge: boolean" in types
    assert 'automatic_merge": False' in service
    assert 'fuzzy_name_matching": False' in service
    assert "api.post" not in api[api.index("getDuplicateDetection"):api.index("getBookingCalendar")]
    assert "api.patch" not in api[api.index("getDuplicateDetection"):api.index("getBookingCalendar")]
    assert "db.add(" not in router
    assert "db.delete(" not in router
    assert "db.commit(" not in router


def test_duplicate_detection_does_not_add_a_database_migration() -> None:
    service = _read(BACKEND / "services" / "cdas_duplicate_detection.py")
    assert "build_duplicate_detection" in service
    assert "alembic" not in service.lower()
