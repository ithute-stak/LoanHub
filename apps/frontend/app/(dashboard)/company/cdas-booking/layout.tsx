import Link from "next/link";
import type { ReactNode } from "react";

export default function CdasBookingLayout({ children }: { children: ReactNode }) {
  return <div className="space-y-4">
    <nav className="flex flex-wrap items-center gap-2 rounded-xl border bg-muted/20 p-2" aria-label="CDAS workspace">
      <Link href="/company/cdas-booking/management-dashboard" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Management Dashboard</Link>
      <Link href="/company/cdas-booking" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Booking Centre</Link>
      <Link href="/company/cdas-booking/bulk-processing" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Bulk Processing</Link>
      <Link href="/company/cdas-booking/advanced-search" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Advanced Search</Link>
      <Link href="/company/cdas-booking/audit-trail" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Audit Trail</Link>
      <Link href="/company/cdas-booking/clients" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Client Profiles</Link>
      <Link href="/company/cdas-booking/duplicates" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Duplicate Detection</Link>
      <Link href="/company/cdas-booking/changes" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Change Detection</Link>
      <Link href="/company/cdas-booking/data-quality" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Data Quality Centre</Link>
      <Link href="/company/cdas-booking/calendar" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Booking Calendar</Link>
      <Link href="/company/cdas-booking/forecast" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">CDAS Forecast</Link>
      <Link href="/company/cdas-booking/priorities" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Priority Queue</Link>
      <Link href="/company/cdas-booking/pipeline" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Opportunity Pipeline</Link>
      <Link href="/company/cdas-booking/follow-ups" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Contact & Follow-Ups</Link>
      <Link href="/company/cdas-booking/officer-performance" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Officer Performance</Link>
      <Link href="/company/cdas-booking/failures" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Failure Tracking</Link>
      <Link href="/company/cdas-booking/simulator" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">What-If Simulator</Link>
      <Link href="/company/cdas-booking/max-loan" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Loan Reference Calculator</Link>
      <Link href="/company/cdas-booking/agency-intelligence" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Agency Intelligence</Link>
      <Link href="/company/cdas-booking/employer-intelligence" className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted">Employer Intelligence</Link>
    </nav>
    {children}
  </div>;
}
