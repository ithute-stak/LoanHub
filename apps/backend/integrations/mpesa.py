"""Optional M-Pesa adapter boundary.

LoanHub remains cash-first. This adapter is a safe extension point and does not
send funds until provider-specific code and credentials are supplied after UAT.
"""

from __future__ import annotations

from integrations.base import IntegrationResult, PaymentGateway


class MpesaPaymentGateway(PaymentGateway):
    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled

    async def initiate(self, instruction: dict) -> IntegrationResult:
        return IntegrationResult(
            status="disabled" if not self.enabled else "configuration_required",
            message="M-Pesa live calls are disabled until the approved market adapter is implemented.",
        )

    async def verify(self, reference: str) -> IntegrationResult:
        return IntegrationResult(
            status="disabled" if not self.enabled else "configuration_required",
            reference=reference,
        )
