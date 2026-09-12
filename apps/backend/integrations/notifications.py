"""SMS and email provider boundaries used by origination events."""

from __future__ import annotations

from integrations.base import IntegrationResult, NotificationGateway


class ConfigurableNotificationGateway(NotificationGateway):
    def __init__(self, *, sms_enabled: bool = False, email_enabled: bool = False) -> None:
        self.sms_enabled = sms_enabled
        self.email_enabled = email_enabled

    async def send_sms(self, destination: str, message: str) -> IntegrationResult:
        return IntegrationResult(
            status="configuration_required" if self.sms_enabled else "disabled",
            message="Configure the approved SMS transport before enabling delivery.",
        )

    async def send_email(self, destination: str, subject: str, body: str) -> IntegrationResult:
        return IntegrationResult(
            status="configuration_required" if self.email_enabled else "disabled",
            message="Configure the approved email transport before enabling delivery.",
        )
