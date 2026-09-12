"""Optional DebiCheck mandate adapter boundary."""

from __future__ import annotations

from integrations.base import IntegrationResult, MandateGateway


class DebiCheckMandateGateway(MandateGateway):
    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled

    async def create_mandate(self, instruction: dict) -> IntegrationResult:
        return IntegrationResult(
            status="disabled" if not self.enabled else "configuration_required",
            message="DebiCheck is market-specific and requires an approved bank/provider adapter.",
        )
