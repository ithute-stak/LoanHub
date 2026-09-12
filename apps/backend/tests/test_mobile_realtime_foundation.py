from pathlib import Path

from api.v1.router import api_router
from services.realtime_event_service import build_realtime_event


APPS_ROOT = Path(__file__).resolve().parents[2]
MOBILE_ROOT = APPS_ROOT / "call_mobile"
MOBILE_LIB = MOBILE_ROOT / "lib"


def _route_pairs(routes) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for route in routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if methods and path:
            pairs.update((method, path) for method in methods)
        effective_candidates = getattr(route, "effective_candidates", None)
        if callable(effective_candidates):
            pairs.update(_route_pairs(effective_candidates()))
    return pairs


def test_realtime_device_registration_routes_are_composed() -> None:
    routes = _route_pairs(api_router.routes)
    assert ("GET", "/realtime/configuration") in routes
    assert ("POST", "/realtime/devices/register") in routes
    assert ("DELETE", "/realtime/devices/{device_uuid}") in routes


def test_realtime_event_envelope_is_typed_and_backwards_compatible() -> None:
    event = build_realtime_event(
        "MONEY_RECEIVED",
        domain="money",
        entity_id="payment-1",
        data={"amount": "250.00", "currency": "LSL"},
        notification={
            "category": "money",
            "title": "Money received",
            "body": "LSL 250.00 received in LoanHub",
            "route": "money:payment-1",
        },
    )
    assert event["type"] == "MONEY_RECEIVED"
    assert event["domain"] == "money"
    assert event["entity_id"] == "payment-1"
    assert event["data"]["amount"] == "250.00"
    assert event["amount"] == "250.00"
    assert event["event_id"]
    assert event["occurred_at"]
    assert event["notification"]["category"] == "money"


def test_mobile_uses_one_socket_and_bloc_event_pipeline_without_chat_pollers() -> None:
    repository = (MOBILE_LIB / "realtime" / "realtime_repository.dart").read_text(
        encoding="utf-8"
    )
    scope = (MOBILE_LIB / "realtime" / "realtime_scope.dart").read_text(
        encoding="utf-8"
    )
    chat_page = (MOBILE_LIB / "features" / "chats" / "chats_page.dart").read_text(
        encoding="utf-8"
    )
    shell = (MOBILE_LIB / "super_app_home.dart").read_text(encoding="utf-8")

    assert "IOWebSocketChannel.connect" in repository
    assert "loanhub.jwt.$token" in repository
    assert "RealtimeBloc" in scope
    assert "ChatBloc" in scope
    assert "MoneyBloc" in scope
    assert "NotificationBloc" in scope
    assert "Timer.periodic" not in chat_page
    assert "Timer.periodic" not in shell


def test_background_notification_channels_cover_messages_money_calls_and_events() -> None:
    activity = (
        MOBILE_ROOT
        / "android"
        / "app"
        / "src"
        / "main"
        / "kotlin"
        / "ls"
        / "ithute"
        / "loanhub"
        / "MainActivity.kt"
    ).read_text(encoding="utf-8")
    manifest = (
        MOBILE_ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    ).read_text(encoding="utf-8")

    for channel in (
        "loanhub_messages",
        "loanhub_money",
        "loanhub_calls",
        "loanhub_events",
    ):
        assert channel in activity
    assert "POST_NOTIFICATIONS" in manifest
    assert "default_notification_channel_id" in manifest


def test_background_push_is_optional_transport_not_a_fake_persistent_socket() -> None:
    main = (MOBILE_LIB / "main.dart").read_text(encoding="utf-8")
    repository = (MOBILE_LIB / "realtime" / "realtime_repository.dart").read_text(
        encoding="utf-8"
    )
    push = (MOBILE_LIB / "realtime" / "push_service.dart").read_text(
        encoding="utf-8"
    )

    assert "FirebaseMessaging.onBackgroundMessage" in push
    assert "FirebaseMessaging.onMessage" in push
    assert "Workmanager" in main
    assert "Background delivery is handed to FCM" in repository
    assert "Future<void> pause()" in repository


def test_money_received_notification_requires_provider_success_path() -> None:
    router = (
        APPS_ROOT / "backend" / "routers" / "lelefa_paygate.py"
    ).read_text(encoding="utf-8")
    money = (APPS_ROOT / "backend" / "routers" / "loanhub_money.py").read_text(
        encoding="utf-8"
    )

    assert "payment.status == PaymentStatus.SUCCEEDED" in router
    assert '"MONEY_RECEIVED"' in router
    assert "realtime_money_received_notified" in router
    assert "status=PaymentStatus.PENDING" in money
    assert '"MONEY_RECEIVED"' not in money
