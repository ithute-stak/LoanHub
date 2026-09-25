import importlib

from core.route_inspection import iter_http_route_pairs


def test_backend_application_imports_cleanly():
    module = importlib.import_module("main")
    assert module.app.title == "LoanHub API"

    route_pairs = list(iter_http_route_pairs(module.app))
    assert route_pairs.count(("GET", "/health/ready")) == 1
    assert route_pairs.count(("GET", "/health")) == 1
