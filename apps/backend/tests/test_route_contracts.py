from __future__ import annotations

import inspect

from main import app
from core.route_inspection import iter_http_route_pairs, methods_for_path
from routers import loan_offers, loans, person


def _methods(path: str) -> set[str]:
    return methods_for_path(app, path)


def test_critical_frontend_backend_routes_are_registered() -> None:
    assert "GET" in _methods("/api/v1/analytics/company")
    assert "GET" in _methods("/api/v1/analytics/platform")
    assert "GET" in _methods("/api/v1/analytics/borrower")
    assert "POST" in _methods("/api/v1/loans/calculator")


def test_active_role_header_is_supported_by_manual_tenant_routes() -> None:
    functions = [
        loan_offers.list_offers_by_request,
        loan_offers.get_offer,
        loans.list_loans,
        loans.get_loan,
        person.get_person_by_user_id,
        person.get_person,
        person.create_person,
        person.update_person,
    ]
    for function in functions:
        assert "x_active_role" in inspect.signature(function).parameters, function.__name__


def test_no_duplicate_http_method_and_path_pairs() -> None:
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for key in iter_http_route_pairs(app):
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    assert not duplicates, f"Duplicate routes: {duplicates}"
