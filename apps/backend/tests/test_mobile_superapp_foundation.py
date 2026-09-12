from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.router import api_router
from routers.loanhub_money import MoneyTransferCreate
from routers.mobile_onboarding import InterestedClientCreate


APPS_ROOT = Path(__file__).resolve().parents[2]
MOBILE = APPS_ROOT / "call_mobile" / "lib"


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


def test_superapp_routes_are_registered() -> None:
    routes = _route_pairs(api_router.routes)
    assert ("GET", "/loanhub-money/configuration") in routes
    assert ("GET", "/loanhub-money/transfers") in routes
    assert ("POST", "/loanhub-money/transfers") in routes
    assert ("POST", "/mobile-onboarding/interested-client") in routes
    assert ("GET", "/chat/conversations") in routes


def test_money_transfer_contract_supports_requested_flows() -> None:
    for transfer_type in ("c2c", "c2b", "b2c", "b2b"):
        payload = MoneyTransferCreate(
            transfer_type=transfer_type,
            amount="25.50",
            counterparty_phone="+26650000000",
        )
        assert payload.transfer_type == transfer_type
        assert str(payload.amount) == "25.50"
        assert payload.currency == "LSL"


def test_money_transfer_rejects_zero_amount() -> None:
    with pytest.raises(ValidationError):
        MoneyTransferCreate(
            transfer_type="c2c",
            amount="0",
            counterparty_phone="+26650000000",
        )


def test_interested_client_signup_is_intentionally_lightweight() -> None:
    payload = InterestedClientCreate(
        first_name="Neo",
        last_name="Mokoena",
        phone="+26650000000",
        password="strong-passphrase",
    )
    assert payload.email is None
    assert payload.phone == "+26650000000"


def test_flutter_superapp_keeps_chat_call_money_explore_and_profile_surfaces() -> None:
    shell = (MOBILE / "super_app_home.dart").read_text(encoding="utf-8")
    for label in ("Chats", "Calls", "Money", "You"):
        assert f"label: '{label}'" in shell

    assert "ChatsPage(api: widget.api)" in shell
    assert "CallsPage(" in shell
    assert "MoneyPage(api: widget.api)" in shell
    assert "ProfilePage(" in shell

    # Explore is intentionally opened from the role workspace / company-channel
    # menu rather than consuming another permanent bottom-navigation slot.
    assert "case MobileWorkspaceDestination.explore:" in shell
    assert "ExplorePage(api: widget.api)" in shell
    assert "value == 'channels'" in shell

    chats = (MOBILE / "features" / "chats" / "chats_page.dart").read_text(
        encoding="utf-8"
    )
    money = (MOBILE / "features" / "money" / "money_page.dart").read_text(
        encoding="utf-8"
    )
    calls = (MOBILE / "features" / "calls" / "calls_page.dart").read_text(
        encoding="utf-8"
    )
    assert "ChatBloc" in chats and "chatConversations" not in shell
    assert "MoneyBloc" in money and "createMoneyTransfer" in money
    assert "LoanHub Business Calls" in calls


def test_mobile_login_no_longer_requires_company_membership() -> None:
    source = (MOBILE / "api" / "loanhub_api.dart").read_text(encoding="utf-8")
    assert "does not have an active LoanHub company membership" not in source
    assert "does not have a LoanHub calling role" not in source
    assert "calling_enabled" in source
