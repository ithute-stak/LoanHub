import Link from "next/link";
import { ArrowRight, CreditCard, Scale, Wallet } from "lucide-react";

import { CashPaymentsPage } from "@/components/payments/cash-payments-page";
import { Button } from "@/components/ui/button";

export default function CompanyPaymentsPage() {
  return (
    <div className="space-y-6">
      <header className="rounded-2xl border bg-card px-5 py-6 shadow-sm sm:px-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <CreditCard aria-hidden="true" className="h-4 w-4" />
              Financial operations
            </div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Payments workspace
            </h1>
            <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
              Review disbursements, borrower repayments, fee settlements and verified payment records for the active company.
            </p>
          </div>
          <nav aria-label="Related finance workspaces" className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <Button asChild variant="outline" className="w-full justify-between sm:w-auto">
              <Link href="/company/finance-desk">
                <Wallet aria-hidden="true" className="mr-2 h-4 w-4" />
                Daily Finance Desk
                <ArrowRight aria-hidden="true" className="ml-2 h-4 w-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full justify-between sm:w-auto">
              <Link href="/company/reconciliation">
                <Scale aria-hidden="true" className="mr-2 h-4 w-4" />
                Reconciliation centre
                <ArrowRight aria-hidden="true" className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </nav>
        </div>
      </header>
      <CashPaymentsPage
        title="Company payments"
        description="Review loan disbursements, borrower repayments, fee settlements, payment channels and manually verified proof for the active company."
      />
    </div>
  );
}
