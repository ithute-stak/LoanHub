import Link from "next/link";
import { AccountingDashboard } from "@/components/accounting/accounting-dashboard";
import { FinancialBooksWorkspace } from "@/components/accounting/financial-books-workspace";

export default function Page() {
  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-primary/5 p-4"><div><p className="font-bold">Looking for daily expenses and loan activity?</p><p className="text-sm text-muted-foreground">Use the simplified Daily Finance Desk for daily entries and reporting.</p></div><Link href="/company/finance-desk" className="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-primary-foreground">Open Daily Finance Desk</Link></div>
      <FinancialBooksWorkspace />
      <AccountingDashboard mode="company" />
    </div>
  );
}
