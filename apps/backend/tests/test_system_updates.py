from main import app
from core.access_control import require_platform_owner
from core.route_inspection import find_http_route


def _route(path: str, method: str):
    route = find_http_route(app, path, method)
    if route is None:
        raise AssertionError(f"Route not found: {method} {path}")
    return route


def test_system_update_routes_are_registered() -> None:
    assert _route("/api/v1/system-updates/status", "GET")
    assert _route("/api/v1/system-updates/update", "POST")


def test_system_update_routes_require_platform_owner() -> None:
    for path, method in (
        ("/api/v1/system-updates/status", "GET"),
        ("/api/v1/system-updates/update", "POST"),
    ):
        route = _route(path, method)
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        assert require_platform_owner in dependencies
