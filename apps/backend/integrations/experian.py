"""Experian adapter boundary.

The class deliberately refuses live traffic until an approved tenant integration
implements the contracted endpoint, authentication and permissible-purpose fields.
This keeps the core lending workflow usable with manual bureau reports.
"""

from __future__ import annotations

from integrations.base import CreditBureauGateway, IntegrationResult


class ExperianCreditBureauGateway(CreditBureauGateway):
    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled

    async def request_report(self, applicant: dict, consent_reference: str) -> IntegrationResult:
        if not self.enabled:
            return IntegrationResult(
                status="disabled",
                message="Experian is not enabled. Record a manual bureau review or configure an approved adapter.",
            )
        return IntegrationResult(
            status="configuration_required",
            message="Add the contracted Experian request/response mapping before enabling production traffic.",
        )
