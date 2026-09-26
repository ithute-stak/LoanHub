import Link from "next/link";
import type { ReactNode } from "react";

export default function CompanyContractsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="sticky top-0 z-20 border-b bg-background/95 px-4 py-2 backdrop-blur md:px-6">
        <nav className="mx-auto flex w-full max-w-[1500px] flex-wrap items-center gap-2 text-sm" aria-label="Contract workspace">
          <Link href="/company/contracts" className="rounded-lg border px-3 py-2 font-medium hover:bg-muted">Contracts</Link>
          <Link href="/company/contracts/signed-upload" className="rounded-lg border px-3 py-2 font-medium hover:bg-muted">Upload signed contracts</Link>
        </nav>
      </div>
      {children}
    </div>
  );
}
