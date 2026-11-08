"""Contractual provider vs platform fee separation; never invents provider fees."""
from dataclasses import dataclass
from decimal import Decimal
from remaining_engine.contracts import ContractError, amount, Money

@dataclass(frozen=True,slots=True)
class CommercialTerms:
    agreement_reference: str
    company_id: str
    operation: str
    fixed_fee: Decimal
    percentage_bps: int
    maximum_fee: Decimal
    approved: bool
    provider_fee_source: str

@dataclass(frozen=True,slots=True)
class FeeQuote:
    principal: Money
    platform_fee: Money
    provider_fee: Money | None
    total_customer_debit: Money | None
    provider_fee_verified: bool

def quote_fees(principal: Money, terms: CommercialTerms,
               *, verified_provider_fee: Money | None = None) -> FeeQuote:
    if not terms.approved or not terms.agreement_reference or not terms.company_id:
        raise ContractError('Written approved commercial terms required')
    if terms.operation not in {'collection','payout'}:
        raise ContractError('Unapproved operation')
    amount(terms.fixed_fee, positive=False)
    amount(terms.maximum_fee, positive=False)
    if type(terms.percentage_bps) is not int or not 0<=terms.percentage_bps<=10000:
        raise ContractError('Invalid basis points')
    if not terms.provider_fee_source:
        raise ContractError('Provider fee evidence source required')
    percentage = (principal.value * Decimal(terms.percentage_bps) / Decimal(10000)).quantize(Decimal('0.01'))
    platform = min(terms.fixed_fee+percentage, terms.maximum_fee)
    if platform < 0:
        raise ContractError('Negative platform fee')
    if verified_provider_fee is not None and verified_provider_fee.currency != principal.currency:
        raise ContractError('Provider fee currency mismatch')
    # Total customer debit must not be computed before determining who legally bears each fee.
    return FeeQuote(principal, Money(platform), verified_provider_fee, None,
                    verified_provider_fee is not None)
