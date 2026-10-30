"""Versioned arrears-policy selection, isolated from live posting.

Company defaults and product overrides are inputs from future tenant-scoped
persistence. Loan-level snapshots are immutable and must be stored at origination.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .policy import ArrearsPolicy, ArrearsRule


@dataclass(frozen=True)
class PolicySelection:
    rule: ArrearsRule
    periodic_arrears_rate_percent: Decimal = Decimal("0")
    additional_interest_authorized: bool = False
    version: int = 1

    def __post_init__(self) -> None:
        rate = Decimal(str(self.periodic_arrears_rate_percent))
        if self.version < 1 or not rate.is_finite() or not (Decimal("0") <= rate <= Decimal("100")):
            raise ValueError("Invalid arrears policy version or interest rate")
        if self.rule != ArrearsRule.CARRY_WITH_INTEREST and (rate != 0 or self.additional_interest_authorized):
            raise ValueError("Only the interest-bearing policy may set arrears interest")
        if self.rule == ArrearsRule.CARRY_WITH_INTEREST and not self.additional_interest_authorized:
            raise ValueError("Interest-bearing policy requires verified authorization")

    def snapshot(self) -> dict[str, str | bool | int]:
        return {
            "rule": self.rule.value,
            "version": self.version,
            "periodic_arrears_rate_percent": str(Decimal(str(self.periodic_arrears_rate_percent))),
            "additional_interest_authorized": self.additional_interest_authorized,
        }

    def to_policy(self) -> ArrearsPolicy:
        return ArrearsPolicy(
            rule=self.rule,
            version=self.version,
            periodic_arrears_rate_percent=Decimal(str(self.periodic_arrears_rate_percent)),
            additional_interest_authorized=self.additional_interest_authorized,
        )


def resolve_new_loan_policy(
    *, company_default: PolicySelection | None,
    product_override: PolicySelection | None,
) -> PolicySelection:
    """Resolve only for new agreements; never recalculate an existing loan."""
    return product_override or company_default or PolicySelection(rule=ArrearsRule.SIMPLE_CARRY)


def read_loan_policy_snapshot(value: dict) -> PolicySelection:
    """Rehydrate the exact policy previously agreed for a particular loan."""
    return PolicySelection(
        rule=ArrearsRule(value["rule"]),
        version=int(value["version"]),
        periodic_arrears_rate_percent=Decimal(str(value["periodic_arrears_rate_percent"])),
        additional_interest_authorized=value["additional_interest_authorized"] is True,
    )
