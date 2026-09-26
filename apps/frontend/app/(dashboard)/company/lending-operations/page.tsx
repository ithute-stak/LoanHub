import Link from "next/link";
import { FileClock, Gavel } from "lucide-react";

import { LendingOperationsPage } from "@/components/lending-operations/lending-operations-page";

export default function CompanyLendingOperationsPage() {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap justify-end gap-2">
        <Link href="/company/credit-committee" className="inline-flex h-11 items-center gap-2 rounded-xl border bg-card px-4 text-sm font-black shadow-sm transition hover:bg-muted">
          <Gavel className="h-4 w-4 text-primary" /> Credit Committee
        </Link>
        <Link href="/company/borrower-requests" className="inline-flex h-11 items-center gap-2 rounded-xl border bg-card px-4 text-sm font-black shadow-sm transition hover:bg-muted">
          <FileClock className="h-4 w-4 text-primary" /> Borrower service requests
        </Link>
      </div>
      <LendingOperationsPage />
    </div>
  );
}
