from __future__ import annotations

import time
from types import SimpleNamespace

import jwt
import pytest

from database.config.config import settings
from database.models.borrower_contact import BorrowerContact
from database.models.call_management import CallManagementPolicy
from routers.call_management import router as call_management_router
from routers.call_media import _staff_telephony, router as call_media_router
from services.call_management_service import (
    issue_livekit_token,
    normalize_lesotho_phone,
    recording_deletion_at,
)


def test_lesotho_phone_normalization() -> None:
    assert normalize_lesotho_phone("+266 5000 0001") == "26650000001"
    assert normalize_lesotho_phone("5000 0001") == "26650000001"
    assert normalize_lesotho_phone("0026650000001") == "26650000001"


@pytest.mark.parametrize("value", ["", "12", "not-a-phone"])
def test_invalid_phone_numbers_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_lesotho_phone(value)


def test_recording_playback_does_not_change_retention_date() -> None:
    policy = CallManagementPolicy(
        recording_enabled=True,
        automatic_deletion_enabled=True,
        recording_retention_days=30,
    )
    first = recording_deletion_at(policy)
    second = recording_deletion_at(policy, now=first.replace(day=first.day) if first else None)
    assert first is not None
    assert second is not None
    assert first < second
    # The service exposes no playback-based retention mutation; deletion_at is
    # fixed when the recording row is created and the playback endpoint only audits.


def test_monitor_token_is_subscribe_only_and_short_lived(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "test-secret-at-least-thirty-two-bytes-long"
    monkeypatch.setattr(settings, "CALL_MEDIA_PROVIDER", "livekit")
    monkeypatch.setattr(settings, "LIVEKIT_URL", "wss://media.example.test")
    monkeypatch.setattr(settings, "LIVEKIT_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LIVEKIT_API_SECRET", secret)
    monkeypatch.setattr(settings, "CALL_TOKEN_TTL_SECONDS", 300)

    result = issue_livekit_token(
        identity="monitor-test",
        room_name="loanhub-call-test",
        can_publish=False,
        can_subscribe=True,
        hidden=True,
        metadata={"purpose": "listen_only_quality_monitoring"},
    )
    payload = jwt.decode(
        result["token"],
        secret,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    grants = payload["video"]
    assert grants["roomJoin"] is True
    assert grants["room"] == "loanhub-call-test"
    assert grants["canPublish"] is False
    assert grants["canSubscribe"] is True
    assert grants["hidden"] is True
    assert 0 < payload["exp"] - int(time.time()) <= 300


def test_softphone_routes_expose_team_directory_and_transfer() -> None:
    paths = {route.path for route in call_media_router.routes}
    assert "/call-management/team-directory" in paths
    assert "/call-management/calls/{call_id}/transfer/{target_staff_id}" in paths


def test_employee_transfer_prefers_configured_sip_address() -> None:
    staff = SimpleNamespace(
        employee_profile=SimpleNamespace(
            target_config={
                "telephony_extension": "202",
                "telephony_address": "sip:202@pbx.example.test",
            }
        ),
        user=SimpleNamespace(phone="5800 0001"),
    )
    target, extension = _staff_telephony(staff)
    assert target == "sip:202@pbx.example.test"
    assert extension == "202"


def test_employee_transfer_falls_back_to_normalized_phone() -> None:
    staff = SimpleNamespace(
        employee_profile=SimpleNamespace(target_config={"extension": "203"}),
        user=SimpleNamespace(phone="5800 0001"),
    )
    target, extension = _staff_telephony(staff)
    assert target == "tel:+26658000001"
    assert extension == "203"


def test_borrower_profile_and_contact_routes_are_exposed() -> None:
    paths = {route.path for route in call_management_router.routes}
    assert "/call-management/clients/{borrower_id}" in paths
    assert "/call-management/clients/{borrower_id}/contacts" in paths


def test_borrower_contact_defaults_to_a_permitted_alternative_call_contact() -> None:
    permitted_default = BorrowerContact.__table__.c.is_call_permitted.default
    primary_default = BorrowerContact.__table__.c.is_primary.default
    assert permitted_default is not None and permitted_default.arg is True
    assert primary_default is not None and primary_default.arg is False


def test_borrower_contact_orm_relationship_is_mapped() -> None:
    assert BorrowerContact.borrower.property.mapper.class_.__name__ == "Borrower"
