"""Phase 91: employee form metadata covers every field and never allows writes."""
from collections import Counter
from inspect import signature
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from core.access_control import TenantContext
from database.models.enums import UserRole
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from routers.batlokoa_registration_availability import (
    get_registration_form_requirements,
    registration_form_requirements_for_staff,
    router,
)


def staff(*, role=UserRole.LOAN_OFFICER, active=True, branch=True):
    actor, company, branch_id = uuid4(), uuid4(), uuid4()
    return TenantContext(
        user=SimpleNamespace(id=actor, is_active=True, role=role),
        staff=SimpleNamespace(
            user_id=actor, company_id=company, is_active=active,
            role=role, branch_id=branch_id if branch else None,
        ),
        company=None, company_id=company,
        branch_id=branch_id if branch else None, is_platform_admin=False,
    )


def test_full_form_contract_has_exactly_one_field_in_each_section():
    r = registration_form_requirements_for_staff(staff())
    keys = [key for section in r.sections for key in section.fields]
    counts = Counter(keys)
    assert set(keys) == set(FullNewOnlyClientCapture.model_fields)
    assert all(n == 1 for n in counts.values())
    assert len({section.id for section in r.sections}) == len(r.sections)


def test_deferred_fields_reflect_disabled_internal_full_writer():
    r = registration_form_requirements_for_staff(staff())
    deferred = set(key for section in r.sections for key in section.deferred_fields)
    assert deferred == {
        "email", "temporary_password", "cdas_employee_number",
        "employer_group_id", "new_employer_group",
    }
    assert all(
        set(section.deferred_fields).issubset(section.fields)
        for section in r.sections
    )


def test_information_is_constant_without_customer_values_or_submit_permission():
    r = registration_form_requirements_for_staff(staff())
    assert r.schema_version == 1
    assert r.registration_available is False
    assert r.submit_allowed is False
    assert r.client_data_requested is False
    assert r == registration_form_requirements_for_staff(staff())
    assert "password_hash" not in r.model_dump_json()
    assert "national_id_normalized" not in r.model_dump_json()


@pytest.mark.parametrize("context", [
    staff(role=UserRole.BORROWER),
    staff(role=UserRole.AUDITOR),
    staff(active=False),
    staff(branch=False),
])
def test_unauthorized_employee_cannot_read_requirements(context):
    with pytest.raises(HTTPException) as error:
        registration_form_requirements_for_staff(context)
    assert error.value.status_code == 403


def test_requirements_api_is_read_only_and_accepts_no_client_body():
    route = next(
        entry for entry in router.routes
        if getattr(entry, "path", "") == "/batlokoa/registration/form-requirements"
    )
    assert route.methods == {"GET"}
    assert list(signature(get_registration_form_requirements).parameters) == ["context"]
    assert route.body_field is None
