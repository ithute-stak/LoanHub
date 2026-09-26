import Link from "next/link";
import { BookOpenCheck, Building2, Gavel, HandCoins } from "lucide-react";
import type { ReactNode } from "react";

export default function CompanyLoansLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-4">
      <nav className="flex flex-wrap items-center gap-2 rounded-2xl border bg-card p-2 shadow-sm" aria-label="Loan register navigation">
        <Link href="/company/loans" className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-black hover:bg-muted">
          <HandCoins className="h-4 w-4" /> Loan portfolio
        </Link>
        <Link href="/company/folio-book" className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-black text-primary hover:bg-primary/5">
          <BookOpenCheck className="h-4 w-4" /> Folio Book
        </Link>
        <Link href="/company/employer-payroll" className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-black text-primary hover:bg-primary/5">
          <Building2 className="h-4 w-4" /> Employer & payroll
        </Link>
        <Link href="/company/credit-committee" className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-black text-primary hover:bg-primary/5">
          <Gavel className="h-4 w-4" /> Credit Committee
        </Link>
      </nav>
      {children}
    </div>
  );
}
