from fastapi import APIRouter, FastAPI

from core.route_inspection import (
    find_http_route,
    iter_http_route_pairs,
    methods_for_path,
    validate_http_route_contracts,
)


def _nested_app() -> FastAPI:
    leaf = APIRouter(prefix="/analytics")

    @leaf.get("/company")
    def company():
        return {"ok": True}

    api = APIRouter()
    api.include_router(leaf)

    app = FastAPI()
    app.include_router(api, prefix="/api/v1")
    return app


def test_route_inspection_resolves_nested_include_prefixes() -> None:
    app = _nested_app()
    assert ("GET", "/api/v1/analytics/company") in set(iter_http_route_pairs(app))
    assert methods_for_path(app, "/api/v1/analytics/company") == {"GET"}
    assert find_http_route(app, "/api/v1/analytics/company", "GET") is not None


def test_route_contract_validation_accepts_nested_router_graph() -> None:
    app = _nested_app()
    validate_http_route_contracts(
        app,
        required={("GET", "/api/v1/analytics/company")},
    )
