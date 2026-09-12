import Link from "next/link";
import type { ReactNode } from "react";
import { ContactRound, UsersRound } from "lucide-react";

export default function CompanyClientsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="space-y-4">
      <section className="rounded-2xl border bg-card p-3 shadow-sm sm:p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Borrower operations</p>
            <p className="mt-1 text-sm font-semibold">The client register and the borrower command centre now work as one workflow.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/company/clients" className="inline-flex items-center gap-2 rounded-xl border bg-muted/30 px-3 py-2 text-xs font-black transition hover:border-primary/30 hover:bg-primary/5">
              <ContactRound className="h-4 w-4 text-primary" />Client register
            </Link>
            <Link href="/company/borrowers" className="inline-flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-xs font-black text-primary-foreground shadow-sm transition hover:bg-primary/90">
              <UsersRound className="h-4 w-4" />Borrower command centre
            </Link>
          </div>
        </div>
      </section>
      {children}
    </div>
  );
}
