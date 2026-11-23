"""Pure company-wide aggregation of branch daily activity.

No database access: caller must supply authorized, tenant-scoped, deduplicated
branch-day snapshots. Internal transfers cancel in the consolidated view.
"""
from dataclasses import dataclass
from decimal import Decimal

from services.branch_funding_policy import amount


@dataclass(frozen=True)
class BranchDay:
    branch_id: str
    opening: Decimal
    loan_disbursements: Decimal
    repayments: Decimal
    expenses: Decimal
    external_funding_in: Decimal = Decimal("0")
    external_funding_out: Decimal = Decimal("0")
    internal_transfers_in: Decimal = Decimal("0")
    internal_transfers_out: Decimal = Decimal("0")

    def expected_closing(self) -> Decimal:
        return amount(self.opening) + amount(self.repayments) + amount(self.external_funding_in) + amount(self.internal_transfers_in) - amount(self.loan_disbursements) - amount(self.expenses) - amount(self.external_funding_out) - amount(self.internal_transfers_out)


def consolidate_branch_day(rows: list[BranchDay]) -> dict[str, Decimal | int]:
    """Combine a single business date and payment channel across distinct branches.

    Internal transfers must be paired and balanced; otherwise fail rather than
    reporting misleading company cash. Never sum day-end balances over dates.
    """
    ids = [row.branch_id for row in rows]
    if any(not branch_id.strip() for branch_id in ids):
        raise ValueError("Branch identity is required for consolidated reporting")
    nonnegative_fields = (
        "opening", "loan_disbursements", "repayments", "expenses",
        "external_funding_in", "external_funding_out",
        "internal_transfers_in", "internal_transfers_out",
    )
    for row in rows:
        for field in nonnegative_fields:
            if amount(getattr(row, field)) < 0:
                raise ValueError(f"Negative {field} in branch {row.branch_id}")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate branch in consolidated daily statement")
    fields = ("opening", "loan_disbursements", "repayments", "expenses",
              "external_funding_in", "external_funding_out",
              "internal_transfers_in", "internal_transfers_out")
    totals = {field: sum((amount(getattr(row, field)) for row in rows), Decimal("0.00")) for field in fields}
    if totals["internal_transfers_in"] != totals["internal_transfers_out"]:
        raise ValueError("Unbalanced internal branch transfers; reconciliation required")
    closing = sum((row.expected_closing() for row in rows), Decimal("0.00"))
    external_closing = totals["opening"] + totals["repayments"] + totals["external_funding_in"] - totals["loan_disbursements"] - totals["expenses"] - totals["external_funding_out"]
    if closing != external_closing:
        raise ValueError("Combined branch statement does not reconcile")
    return {"branch_count": len(rows), **totals, "expected_closing": closing}
