"""Guard against unsafe Principal x ledger certification from payment rows.

LoanHub PaymentTransaction is not a complete ledger: allocations, cash
collections, treasury, imported legacy records and external reversals may
have independent lifecycles. This contract makes evidence requirements
explicit before any adapter may set reconciled=True.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import FrozenSet

from payment_engine.principal_x_collection_ceiling import money


REQUIRED_SOURCE_FAMILIES: FrozenSet[str] = frozenset({
    "payment_transactions",
    "cash_collections",
    "repayment_allocations",
    "treasury_collections",
    "legacy_imports",
    "provider_reversals",
    "refunds",
    "manual_adjustments",
})


@dataclass(frozen=True)
class LedgerSourceAttestation:
    source_family: str
    complete: bool
    evidence_reference: str
    unresolved_count: int


@dataclass(frozen=True)
class LedgerCompleteness:
    net_collected: Decimal
    reconciled: bool
    source_count: int


def require_authoritative_ledger_attestations(
    *, net_collected: Decimal,
    attestations: tuple[LedgerSourceAttestation, ...],
) -> LedgerCompleteness:
    """Require explicit per-family audit, including proven empty sources.

    This validates attestation structure only. A trusted server adapter must
    obtain evidence from independent authoritative sources, under the same
    loan lock. Never accept attestations from a borrower or API request.
    """
    indexed: dict[str, LedgerSourceAttestation] = {}
    evidence_references: set[str] = set()
    for item in attestations:
        if item.source_family not in REQUIRED_SOURCE_FAMILIES:
            raise ValueError("Unknown ledger source family")
        if item.source_family in indexed:
            raise ValueError("Duplicate ledger source family")
        if item.complete is not True:
            raise ValueError("Incomplete ledger source")
        if not isinstance(item.evidence_reference, str) or not item.evidence_reference.strip():
            raise ValueError("Source audit evidence required")
        # A single evidence reference cannot independently attest two
        # different source families. Normalize spaces before deduplicating.
        reference = item.evidence_reference.strip()
        if reference in evidence_references:
            raise ValueError("Duplicate ledger evidence reference")
        evidence_references.add(reference)
        if type(item.unresolved_count) is not int or item.unresolved_count != 0:
            raise ValueError("Unresolved ledger entries")
        indexed[item.source_family] = item
    missing = REQUIRED_SOURCE_FAMILIES - indexed.keys()
    if missing:
        raise ValueError("Missing authoritative ledger sources: " + ", ".join(sorted(missing)))
    # Certification must not silently round an inconsistent sub-cent
    # lifetime total into an apparently exact financial balance.
    try:
        raw_collected = Decimal(str(net_collected))
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise ValueError("Invalid authoritative net collection") from exc
    if not raw_collected.is_finite():
        raise ValueError("Invalid authoritative net collection")
    if raw_collected < 0:
        raise ValueError("Negative net collections")
    if raw_collected != raw_collected.quantize(Decimal("0.01")):
        raise ValueError("Sub-cent authoritative net collection")
    collected = money(raw_collected)
    return LedgerCompleteness(
        net_collected=collected, reconciled=True,
        source_count=len(indexed),
    )
