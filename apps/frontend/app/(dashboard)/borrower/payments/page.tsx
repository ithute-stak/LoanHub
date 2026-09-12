import { BorrowerOnlinePaymentPanel } from "@/components/borrower/borrower-online-payment-panel";
import { CashPaymentsPage } from "@/components/payments/cash-payments-page";

export default function BorrowerPaymentsPage() {
  return (
    <div className="space-y-6">
      <BorrowerOnlinePaymentPanel />
      <CashPaymentsPage
        title="My payments"
        description="Pay securely through LelefaPayGate and review every approved-loan disbursement or repayment recorded against your borrower account."
      />
    </div>
  );
}
