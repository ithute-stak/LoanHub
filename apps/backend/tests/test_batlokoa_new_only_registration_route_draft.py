"""Future client-write route is explicit, private and non-activating."""
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.v1.router import api_router
from database.models.enums import EmploymentStatus, Gender
from database.schemas.full_new_only_client_capture import FullNewOnlyClientCapture
from routers.batlokoa_new_only_registration_command import (
    create_new_only_client,
    router,
)


def _synthetic_payload():
    return FullNewOnlyClientCapture(
        branch_id=uuid4(), first_name="Test", last_name="Applicant",
        phone="59995555", date_of_birth=date(1990, 1, 1),
        national_id="TEST-ONLY-NOT-A-REAL-ID", gender=Gender.FEMALE,
        district="Maseru", employment_status=EmploymentStatus.EMPLOYED,
        consent_to_share_profile=True, consent_to_credit_checks=True,
    )


def test_draft_route_is_not_mounted_in_public_loanhub_api():
    assert all(
        "/batlokoa/registration/clients" not in getattr(route, "path", "")
        for route in api_router.routes
    )
    assert any(
        getattr(route, "path", "") == "/batlokoa/registration/clients"
        and route.methods == {"POST"} for route in router.routes
    )


def test_draft_route_rejects_even_valid_complete_registration():
    with pytest.raises(HTTPException) as error:
        create_new_only_client(
            payload=_synthetic_payload(),
            context=None,
            idempotency_key="synthetic-replay-key-0001",
        )
    assert error.value.status_code == 503
    assert error.value.detail == {"code": "NEW_ONLY_REGISTRATION_NOT_RELEASED"}


def test_draft_route_rejects_without_idempotency_key():
    with pytest.raises(HTTPException) as error:
        create_new_only_client(
            payload=_synthetic_payload(),
            context=None, idempotency_key=None,
        )
    assert error.value.status_code == 503
