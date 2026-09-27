import Link from "next/link";
import { Scale } from "lucide-react";

import { CashPaymentsPage } from "@/components/payments/cash-payments-page";
import { Button } from "@/components/ui/button";

export default function CompanyPaymentsPage() {
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button asChild variant="outline">
          <Link href="/company/reconciliation">
            <Scale className="mr-2 h-4 w-4" /> Reconciliation centre
          </Link>
        </Button>
      </div>
      <CashPaymentsPage title="Company payments" description="Review loan disbursements, borrower repayments, fee settlements, payment channels and manually verified proof for the active company." />
    </div>
  );
}
