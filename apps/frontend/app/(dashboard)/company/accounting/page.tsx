import { AccountingDashboard } from "@/components/accounting/accounting-dashboard";
import { FinancialBooksWorkspace } from "@/components/accounting/financial-books-workspace";

export default function Page() {
  return (
    <div className="space-y-10">
      <FinancialBooksWorkspace />
      <AccountingDashboard mode="company" />
    </div>
  );
}
