"""Registration-context must never check affordability for a mismatched employee ID."""
from pathlib import Path


ROUTER = Path(__file__).resolve().parents[1] / "routers" / "cdas_api.py"


def test_registration_context_checks_employee_number_before_affordability():
    source = ROUTER.read_text(encoding="utf-8")
    start = source.index("async def get_employee_registration_context(")
    end = source.index('@router.post("/deductions/all")', start)
    method = source[start:end]
    verification = method.index('returned_employee_no.casefold() != employee_no.casefold()')
    affordability = method.index("await client.check_affordability(employee_no)")
    assert verification < affordability
    assert 'status_code=502' in method[verification:affordability]


def test_registration_context_remains_company_scoped_and_needs_verified_profile():
    source = ROUTER.read_text(encoding="utf-8")
    start = source.index("async def get_employee_registration_context(")
    end = source.index('@router.post("/deductions/all")', start)
    method = source[start:end]
    assert "_require_company_manager(context)" in method
    assert "company_id=context.company_id" in method
    assert "_employee_cdas_registration_decision(" in method
