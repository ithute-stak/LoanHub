import Link from "next/link";
import type { ReactNode } from "react";

export default function CdasBookingLayout({ children }: { children: ReactNode }) {
  return <div className="space-y-4">
    <nav className="flex flex-wrap items-center gap-2 rounded-xl border bg-muted/20 p-2" aria-label="CDAS workspace">
      <Link href="/company/cdas-booking" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Booking Centre</Link>
      <Link href="/company/cdas-booking/clients" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Client Profiles</Link>
      <Link href="/company/cdas-booking/calendar" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Booking Calendar</Link>
      <Link href="/company/cdas-booking/priorities" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Priority Queue</Link>
      <Link href="/company/cdas-booking/simulator" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">What-If Simulator</Link>
    </nav>
    {children}
  </div>;
}
