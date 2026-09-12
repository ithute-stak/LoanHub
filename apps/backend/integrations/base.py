from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class IntegrationResult:
    status: str
    reference: str | None = None
    message: str | None = None
    payload: dict[str, Any] | None = None


class CreditBureauGateway(ABC):
    @abstractmethod
    async def request_report(self, applicant: dict[str, Any], consent_reference: str) -> IntegrationResult: ...


class MandateGateway(ABC):
    @abstractmethod
    async def create_mandate(self, instruction: dict[str, Any]) -> IntegrationResult: ...


class NotificationGateway(ABC):
    @abstractmethod
    async def send_sms(self, destination: str, message: str) -> IntegrationResult: ...

    @abstractmethod
    async def send_email(self, destination: str, subject: str, body: str) -> IntegrationResult: ...


class PaymentGateway(ABC):
    @abstractmethod
    async def initiate(self, instruction: dict[str, Any]) -> IntegrationResult: ...

    @abstractmethod
    async def verify(self, reference: str) -> IntegrationResult: ...
