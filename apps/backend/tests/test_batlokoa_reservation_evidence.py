"""Pure chain integrity and cross-tenant isolation contract tests."""
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

import pytest

from services.batlokoa_reservation_evidence import (
    EvidenceIntegrityError, ReservationEvidence, hash_reservation_evidence,
    verify_evidence_chain,
)

COMPANY = UUID("4236a21f-5164-48aa-90f3-a35eccd23ae2")
OTHER = UUID("00000000-0000-4000-8000-000000000002")
RES = UUID("00000000-0000-4000-8000-000000000003")
LOAN = UUID("00000000-0000-4000-8000-000000000004")
BORROWER = UUID("00000000-0000-4000-8000-000000000005")


def genesis():
    return ReservationEvidence(
        company_id=COMPANY, reservation_id=RES, loan_id=LOAN,
        borrower_id=BORROWER, amount=Decimal("100.00"),
        request_fingerprint="a" * 64, event_type="reserved",
        event_sequence=1, previous_digest=None,
    )


def sequence():
    first = genesis()
    second = replace(first, event_type="previewed", event_sequence=2,
                     previous_digest=hash_reservation_evidence(first))
    return first, second


def test_verifies_two_event_chain():
    events = sequence()
    assert verify_evidence_chain(events, hash_reservation_evidence(events[-1]))


def test_wrong_tip_is_not_accepted():
    events = sequence()
    assert verify_evidence_chain(events, "f" * 64) is False


@pytest.mark.parametrize("change", [
    {"amount": Decimal("100.01")},
    {"company_id": OTHER},
    {"loan_id": OTHER},
    {"reservation_id": OTHER},
    {"borrower_id": OTHER},
    {"request_fingerprint": "b" * 64},
])
def test_tampering_breaks_digest_or_tenant_binding(change):
    events = sequence()
    altered = (events[0], replace(events[1], **change))
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_chain(altered, hash_reservation_evidence(events[-1]))


def test_changed_amount_only_changes_digest():
    first = genesis()
    altered = replace(first, amount=Decimal("100.01"))
    assert hash_reservation_evidence(first) != hash_reservation_evidence(altered)


def test_reordering_and_gaps_are_rejected():
    first, second = sequence()
    for events in ((second, first), (first, replace(second, event_sequence=3))):
        with pytest.raises(EvidenceIntegrityError):
            verify_evidence_chain(events, hash_reservation_evidence(second))


def test_first_link_requires_genesis_and_sequence_one():
    for bad in (replace(genesis(), event_sequence=2),
                replace(genesis(), previous_digest="0" * 64)):
        with pytest.raises(EvidenceIntegrityError):
            hash_reservation_evidence(bad)


@pytest.mark.parametrize("bad", [Decimal("-1"), Decimal("NaN"), Decimal("1.001")])
def test_invalid_amounts_rejected(bad):
    with pytest.raises(EvidenceIntegrityError):
        hash_reservation_evidence(replace(genesis(), amount=bad))


def test_no_events_fails_closed():
    with pytest.raises(EvidenceIntegrityError):
        verify_evidence_chain((), "a" * 64)
