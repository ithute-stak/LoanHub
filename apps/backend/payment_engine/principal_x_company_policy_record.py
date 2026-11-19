"""Strict storage representation for Principal x% company policy.

Persist these fields only in a dedicated company payment-policy record after
schema migration; never store them in loan calculator configuration.
"""
from dataclasses import dataclass
from typing import Mapping

from payment_engine.principal_x_policy import PaymentModel, PaymentModelPolicy


@dataclass(frozen=True)
class CompanyPaymentPolicyRecord:
    company_id: str
    default_model: str = "existing"
    allow_new_loans: bool = False
    enable_live_collections: bool = False

    def as_policy(self) -> PaymentModelPolicy:
        try:
            model = PaymentModel(self.default_model)
        except ValueError as exc:
            raise ValueError("Unknown company payment model") from exc
        if type(self.allow_new_loans) is not bool or type(self.enable_live_collections) is not bool:
            raise ValueError("Company payment policy flags must be boolean")
        if self.enable_live_collections and not self.allow_new_loans:
            raise ValueError("Live collections require new-loan eligibility")
        if model == PaymentModel.EXISTING and self.enable_live_collections:
            raise ValueError("Principal x% live collections require an explicit Principal x% default")
        return PaymentModelPolicy(
            company_default=model,
            allow_new_loans=self.allow_new_loans,
            enable_live_collections=self.enable_live_collections,
        )


def parse_company_payment_policy(
    *, company_id: str, stored: Mapping[str, object] | None
) -> CompanyPaymentPolicyRecord:
    """Fail closed for absent or malformed configuration, without changing contracts."""
    if not company_id.strip():
        raise ValueError("Company identity is required")
    if stored is None:
        return CompanyPaymentPolicyRecord(company_id=company_id)
    allowed = {"default_model", "allow_new_loans", "enable_live_collections"}
    if set(stored) - allowed:
        raise ValueError("Unexpected company payment policy fields")
    record = CompanyPaymentPolicyRecord(
        company_id=company_id,
        default_model=stored.get("default_model", "existing"),
        allow_new_loans=stored.get("allow_new_loans", False),
        enable_live_collections=stored.get("enable_live_collections", False),
    )
    record.as_policy()
    return record
