from decimal import Decimal

import pytest

from payment_engine.principal_x_ledger_source_attestation import (
    REQUIRED_SOURCE_FAMILIES,
    LedgerSourceAttestation,
    require_authoritative_ledger_attestations,
)


def evidence():
    return tuple(
        LedgerSourceAttestation(
            source_family=name, complete=True,
            evidence_reference="audit:" + name,
            unresolved_count=0,
        )
        for name in sorted(REQUIRED_SOURCE_FAMILIES)
    )


def test_all_sources_are_required():
    result = require_authoritative_ledger_attestations(
        net_collected=Decimal("1900"), attestations=evidence(),
    )
    assert result.reconciled is True
    assert result.net_collected == Decimal("1900.00")
    assert result.source_count == len(REQUIRED_SOURCE_FAMILIES)


def test_missing_family_fails_closed():
    with pytest.raises(ValueError, match="Missing authoritative"):
        require_authoritative_ledger_attestations(
            net_collected=Decimal("0"), attestations=evidence()[:-1],
        )


@pytest.mark.parametrize("change", [
    {"complete": False},
    {"evidence_reference": ""},
    {"unresolved_count": 1},
    {"unresolved_count": True},
])
def test_bad_attestation_rejected(change):
    original = evidence()
    altered = (LedgerSourceAttestation(
        **{**original[0].__dict__, **change}
    ),) + original[1:]
    with pytest.raises(ValueError):
        require_authoritative_ledger_attestations(
            net_collected=Decimal("100"), attestations=altered,
        )


def test_duplicate_source_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        require_authoritative_ledger_attestations(
            net_collected=Decimal("0"), attestations=evidence() + (evidence()[0],),
        )


def test_negative_collection_rejected():
    with pytest.raises(ValueError, match="Negative"):
        require_authoritative_ledger_attestations(
            net_collected=Decimal("-1"), attestations=evidence(),
        )


@pytest.mark.parametrize("reference", [
    "audit:" + sorted(REQUIRED_SOURCE_FAMILIES)[1],
    " audit:" + sorted(REQUIRED_SOURCE_FAMILIES)[1] + " ",
])
def test_reused_audit_reference_across_distinct_families_fails_closed(reference):
    original = evidence()
    assert original[0].source_family != original[1].source_family
    altered = (LedgerSourceAttestation(
        **{**original[0].__dict__, "evidence_reference": reference}
    ),) + original[1:]
    with pytest.raises(ValueError, match="Duplicate ledger evidence reference"):
        require_authoritative_ledger_attestations(
            net_collected=Decimal("100.00"), attestations=altered,
        )


def test_unique_evidence_references_are_allowed():
    original = evidence()
    result = require_authoritative_ledger_attestations(
        net_collected=Decimal("20.00"), attestations=original,
    )
    assert result.source_count == len(REQUIRED_SOURCE_FAMILIES)
