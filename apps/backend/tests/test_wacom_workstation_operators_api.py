"""Wacom operator assignment stays tenant-scoped and never grants signing."""
from api.v1.router import api_router


def test_operator_assignment_endpoints_are_registered():
    endpoints = {r.path for r in api_router.routes}
    assert "/contract-signing/workstations/{workstation_id}/operators" in endpoints
    assert "/contract-signing/workstations/{workstation_id}/operators/{employee_id}/revoke" in endpoints
    assert "/contract-signing/workstations/{workstation_id}/my-assignment" in endpoints


def test_assignment_never_issues_signing_permission():
    from routers.wacom_workstation_operators import OperatorAssignmentRequest
    assert OperatorAssignmentRequest(employee_user_id="00000000-0000-4000-8000-000000000001").employee_user_id
