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
