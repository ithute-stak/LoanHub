"""Offline HMAC identity and replay rules for a future durable reservation."""
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from services.batlokoa_new_only_application_idempotency_design import (
    NewOnlyLoanHandoffDenied,
    check_proposed_application_replay,
    prepare_new_only_application_intent,
)


SECRET = b"offline-batlokoa-hmac-secret-not-for-production-2026"


def arguments():
    return dict(
        company_id=uuid4(), branch_id=uuid4(), employee_user_id=uuid4(),
        account_id=uuid4(), product_id=uuid4(),
        principal=Decimal("1000.00"), term_count=3,
        request_key="offline-batlokoa-loan-20261119",
        fingerprint_secret=SECRET,
    )


def replay(intent, **changes):
    stored = dict(
        stored_company_id=intent.company_id,
        stored_request_key=intent.request_key,
        stored_fingerprint=intent.request_fingerprint,
        stored_status="completed",
    )
    stored.update(changes)
    return check_proposed_application_replay(intent, **stored)


def test_canonical_equivalent_values_share_fingerprint_without_loan_creation():
    args = arguments()
    a = prepare_new_only_application_intent(**args)
    b = prepare_new_only_application_intent(**{**args, "principal": Decimal("1000")})
    assert a.request_fingerprint == b.request_fingerprint
    assert len(a.request_fingerprint) == 64
    assert a.can_reserve is False
    assert a.can_create_application is False
    assert a.request_key not in a.request_fingerprint
    assert replay(a) == "previously_completed_no_new_write"


@pytest.mark.parametrize("changed", [
    "company_id", "branch_id", "employee_user_id", "account_id",
    "product_id", "principal", "term_count",
])
def test_reused_request_key_with_changed_payload_is_rejected(changed):
    base = arguments()
    original = prepare_new_only_application_intent(**base)
    modified = dict(base)
    modified[changed] = (
        Decimal("1500.00") if changed == "principal"
        else 4 if changed == "term_count"
        else uuid4()
    )
    changed_intent = prepare_new_only_application_intent(**modified)
    assert original.request_fingerprint != changed_intent.request_fingerprint
    with pytest.raises(NewOnlyLoanHandoffDenied, match="reused"):
        replay(changed_intent, stored_fingerprint=original.request_fingerprint)


@pytest.mark.parametrize("status,expected", [
    ("reserved", "already_reserved_no_new_write"),
    ("completed", "previously_completed_no_new_write"),
    ("rejected", "previously_rejected_no_new_write"),
])
def test_all_replays_are_no_write_outcomes(status, expected):
    intent = prepare_new_only_application_intent(**arguments())
    assert replay(intent, stored_status=status) == expected


def test_untrusted_and_unknown_replay_records_fail_closed():
    intent = prepare_new_only_application_intent(**arguments())
    for row in [
        {"stored_company_id": uuid4()},
        {"stored_request_key": "different-request-key-2026"},
        {"stored_fingerprint": "f" * 64},
        {"stored_fingerprint": None},
        {"stored_status": "unknown"},
    ]:
        with pytest.raises(NewOnlyLoanHandoffDenied):
            replay(intent, **row)


@pytest.mark.parametrize("overrides", [
    {"principal": Decimal("NaN")}, {"principal": Decimal("Infinity")},
    {"principal": Decimal("-1")}, {"principal": Decimal("1000.001")},
    {"principal": "1000.00"}, {"term_count": True},
    {"term_count": 121}, {"request_key": "short"},
    {"request_key": "unsafe key with spaces 2026"},
    {"fingerprint_secret": b"too-short"},
    {"fingerprint_secret": None},
    {"company_id": "untrusted-company"},
])
def test_invalid_intent_rejected_without_any_reservation(overrides):
    with pytest.raises(NewOnlyLoanHandoffDenied):
        prepare_new_only_application_intent(**{**arguments(), **overrides})


def test_hmac_secret_is_part_of_fingerprint_and_key_is_not():
    args = arguments()
    a = prepare_new_only_application_intent(**args)
    b = prepare_new_only_application_intent(**{
        **args, "fingerprint_secret": b"a" * 32,
    })
    c = prepare_new_only_application_intent(**{
        **args, "request_key": "second-request-key-20261119",
    })
    assert a.request_fingerprint != b.request_fingerprint
    assert a.request_fingerprint == c.request_fingerprint
    with pytest.raises(NewOnlyLoanHandoffDenied):
        replay(c, stored_request_key=a.request_key)


def test_forged_intent_cannot_turn_off_persistent_safety_controls():
    intent = prepare_new_only_application_intent(**arguments())
    forged = replace(intent, can_reserve=True, can_create_application=True)
    # No service ever accepts either flag as authorization.
    assert replay(forged) == "previously_completed_no_new_write"
