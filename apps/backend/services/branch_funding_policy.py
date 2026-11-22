"""Pure, fail-closed branch funding policy. Not wired to live posting until integration tests pass.

Balances must be calculated under the same database transaction/branch-channel lock
as the final debit. A preview alone is never authorization to spend.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum


class OpeningMode(str, Enum):
    MANUAL = "manual"
    PREVIOUS_CLOSING = "previous_closing"


@dataclass(frozen=True)
class BranchFundingPolicy:
    opening_mode: OpeningMode = OpeningMode.MANUAL
    require_confirmed_opening: bool = True
    prevent_negative_available_balance: bool = True


class FundingRejected(ValueError):
    """No funds may leave the branch when this check fails."""


def amount(value: Decimal | str | int) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise FundingRejected("Invalid monetary amount") from exc
    if not parsed.is_finite() or parsed.as_tuple().exponent < -2:
        raise FundingRejected("Amounts must be finite and have at most two decimal places")
    return parsed.quantize(Decimal("0.01"))


def opening_is_authorized(*, policy: BranchFundingPolicy, manually_confirmed: bool) -> bool:
    return manually_confirmed or policy.opening_mode == OpeningMode.PREVIOUS_CLOSING


def require_available_funds(
    *,
    opening_confirmed: bool,
    available: Decimal | str | int,
    requested: Decimal | str | int,
    reserved: Decimal | str | int = "0",
    policy: BranchFundingPolicy = BranchFundingPolicy(),
) -> Decimal:
    """Return remaining spendable balance; use for BOTH expense and loan disbursement.

    Caller must scope company, branch, business date and payment channel, and lock
    the balance/reservations before checking and posting the debit atomically.
    """
    if policy.require_confirmed_opening and not opening_confirmed:
        raise FundingRejected("Branch opening balance must be confirmed first")
    balance, debit, held = amount(available), amount(requested), amount(reserved)
    if balance < 0 or debit <= 0 or held < 0:
        raise FundingRejected("Invalid available funds, reservation or debit")
    remaining = balance - held - debit
    if policy.prevent_negative_available_balance and remaining < 0:
        raise FundingRejected("Insufficient branch funds for this payment channel")
    return remaining


def assert_branch_channel_debit(
    *,
    company_id: str,
    branch_id: str,
    channel: str,
    opening_confirmed: bool,
    available: Decimal | str | int,
    debit: Decimal | str | int,
    reserved: Decimal | str | int = "0",
    policy: BranchFundingPolicy = BranchFundingPolicy(),
) -> Decimal:
    """Fail closed on missing tenant, branch or payment channel before debit.

    Integration must obtain these from authenticated tenant-scoped records, not
    from an untrusted client payload. Must execute under an exclusive ledger
    lock in the SAME transaction that posts the outgoing movement.
    """
    if not company_id or not branch_id or not channel:
        raise FundingRejected("Company, branch and payment channel are required")
    return require_available_funds(
        opening_confirmed=opening_confirmed,
        available=available,
        requested=debit,
        reserved=reserved,
        policy=policy,
    )
