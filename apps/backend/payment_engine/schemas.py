"""API validation for the opt-in arrears policy configuration."""
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

from payment_engine.configuration import PolicySelection
from payment_engine.policy import ArrearsRule


class ArrearsPolicyPayload(BaseModel):
    rule: ArrearsRule = ArrearsRule.SIMPLE_CARRY
    version: int = Field(default=1, ge=1)
    periodic_arrears_rate_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=6, decimal_places=3)
    additional_interest_authorized: bool = False

    @model_validator(mode="after")
    def enforce_authorization(self):
        self.to_selection()
        return self

    def to_selection(self) -> PolicySelection:
        return PolicySelection(
            rule=self.rule,
            version=self.version,
            periodic_arrears_rate_percent=self.periodic_arrears_rate_percent,
            additional_interest_authorized=self.additional_interest_authorized,
        )
