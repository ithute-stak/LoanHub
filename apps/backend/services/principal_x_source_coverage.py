"""Explicit, non-authoritative coverage map for Principal x settlement.

A diagnostic query is not an authoritative source reconciliation. In
particular, seeing zero refunds or reversals in PaymentTransaction is not
proof that external, legacy or manual sources are empty.
"""
from dataclasses import dataclass
from typing import Literal

from payment_engine.principal_x_ledger_source_attestation import (
    REQUIRED_SOURCE_FAMILIES,
)

ReviewStage = Literal["diagnostic_only", "authoritative_adapter_missing"]


@dataclass(frozen=True)
class SourceCoverage:
    source_family: str
    review_stage: ReviewStage
    authoritatively_verified: Literal[False] = False


DIAGNOSTIC_SOURCE_FAMILIES = frozenset({
    "payment_transactions",
    "cash_collections",
    "repayment_allocations",
    "treasury_collections",
    "legacy_imports",
    "provider_reversals",
    "refunds",
    "manual_adjustments",
})


def principal_x_source_coverage() -> tuple[SourceCoverage, ...]:
    """Report implementation coverage without claiming lifetime completeness.

    This list is a code-capability inventory, not an examination of the
    current loan or evidence from an independent payment provider.
    """
    if not DIAGNOSTIC_SOURCE_FAMILIES <= REQUIRED_SOURCE_FAMILIES:
        raise ValueError("Unknown diagnostic source families")
    return tuple(
        SourceCoverage(
            source_family=family,
            review_stage=(
                "diagnostic_only"
                if family in DIAGNOSTIC_SOURCE_FAMILIES
                else "authoritative_adapter_missing"
            ),
            authoritatively_verified=False,
        )
        for family in sorted(REQUIRED_SOURCE_FAMILIES)
    )
