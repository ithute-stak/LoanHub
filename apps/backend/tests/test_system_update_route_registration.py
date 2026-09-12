from main import app
from core.route_inspection import iter_http_route_pairs


REQUIRED = {
    ("GET", "/api/v1/system-updates/status"),
    ("POST", "/api/v1/system-updates/update"),
}


def test_system_update_routes_are_exposed_by_main_app() -> None:
    actual = set(iter_http_route_pairs(app))
    missing = REQUIRED - actual
    assert not missing, (
        "System update router is not registered in api/v1/router.py. "
        f"Missing routes: {sorted(missing)}"
    )
