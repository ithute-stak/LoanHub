from __future__ import annotations

from integrations.base import CreditBureauGateway, IntegrationResult, MandateGateway, NotificationGateway, PaymentGateway


class ManualCreditBureauGateway(CreditBureauGateway):
    async def request_report(self, applicant: dict, consent_reference: str) -> IntegrationResult:
        return IntegrationResult(status="manual_review_required", message="Upload and review a lawful bureau report manually.")


class DisabledMandateGateway(MandateGateway):
    async def create_mandate(self, instruction: dict) -> IntegrationResult:
        return IntegrationResult(status="disabled", message="DebiCheck is not enabled for this market/company.")


class DisabledNotificationGateway(NotificationGateway):
    async def send_sms(self, destination: str, message: str) -> IntegrationResult:
        return IntegrationResult(status="disabled")

    async def send_email(self, destination: str, subject: str, body: str) -> IntegrationResult:
        return IntegrationResult(status="disabled")


class CashOnlyPaymentGateway(PaymentGateway):
    async def initiate(self, instruction: dict) -> IntegrationResult:
        return IntegrationResult(status="manual_cash_required", message="Record cash in/out through the LoanHub cash desk.")

    async def verify(self, reference: str) -> IntegrationResult:
        return IntegrationResult(status="manual_cash_required", reference=reference)
