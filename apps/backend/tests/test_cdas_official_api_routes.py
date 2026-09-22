from fastapi import FastAPI

from core.route_inspection import iter_http_route_pairs
from routers.cdas_api import router


def test_official_cdas_router_exposes_documented_operations() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    routes = set(iter_http_route_pairs(app))

    expected = {
        ("GET", "/api/v1/cdas/status"),
        ("POST", "/api/v1/cdas/employees/{employee_no}/details"),
        ("POST", "/api/v1/cdas/employees/{employee_no}/affordability"),
        ("POST", "/api/v1/cdas/employees/{employee_no}/deductions/all"),
        ("POST", "/api/v1/cdas/employees/{employee_no}/deductions/owned"),
        ("POST", "/api/v1/cdas/employees/{employee_no}/active-approved"),
        ("POST", "/api/v1/cdas/employees/{employee_no}/refresh"),
        ("POST", "/api/v1/cdas/deductions/workflow"),
        ("POST", "/api/v1/cdas/deductions/{deduction_id}/modify-active"),
        ("POST", "/api/v1/cdas/deductions/{deduction_id}/settle"),
        ("POST", "/api/v1/cdas/documents"),
    }

    assert expected.issubset(routes)
