"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Building2, FileDown, RefreshCw, ShieldCheck } from "lucide-react";
import { expenseManagementApi } from "@/api/expenseManagement";
import type { TreasuryDashboard, BranchDaySummary } from "@/types/expenseManagement";
import { useTenant } from "@/provider/tenantProvider";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/utils/apiError";

const format = (value: number | string | null | undefined) =>
  "M " + Number(value ?? 0).toLocaleString("en-LS", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const localDay = () => {
  const d = new Date();
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
};

export default function ConsolidatedBranchStatementPage() {
  const { activeCompanyId, activeRole } = useTenant();
  const [businessDate, setBusinessDate] = useState(localDay);
  const [report, setReport] = useState<TreasuryDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = activeRole === "company_owner" || activeRole === "company_admin";

  const load = useCallback(async () => {
    if (!activeCompanyId || !allowed) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      // A company-wide view is only requested by an owner or company admin.
      // Do not provide a branch_id: the existing tenant-scoped API aggregates
      // authorized branches and enforces the company boundary.
      const result = await expenseManagementApi.dashboard(businessDate);
      setReport(result);
    } catch (failure) {
      setError(getErrorMessage(failure, "Unable to load the consolidated branch statement"));
    } finally {
      setLoading(false);
    }
  }, [activeCompanyId, allowed, businessDate]);

  useEffect(() => { void load(); }, [load]);

  const reconciliation = useMemo(() => {
    const branches = report?.branches ?? [];
    const declared = branches.filter((row: BranchDaySummary) => row.declared_closing_balance !== null);
    return {
      declared: declared.length,
      uncounted: branches.length - declared.length,
      variances: declared.reduce((total, row) => total + Number(row.variance_amount), 0),
      unresolved: branches.filter(row => row.pending_entry_count > 0).length,
    };
  }, [report]);

  if (!allowed) {
    return <div className="rounded-2xl border p-6"><h1 className="text-xl font-bold">Company-wide statement</h1>
      <p className="mt-2 text-sm text-muted-foreground">Only a company owner or administrator can view the combined statement. Use your branch&apos;s financial reports for branch-scoped information.</p></div>;
  }

  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4 print:hidden">
      <div className="space-y-2">
        <Link href="/company/finance-desk" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary"><ArrowLeft className="size-4"/>Daily Finance Desk</Link>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Company-wide Branch Financial Statement</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">One view of all branches using LoanHub&apos;s existing treasury ledger. Channel balances, unresolved entries and counted cash differences remain visible.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={loading} onClick={() => void load()}><RefreshCw className="mr-2 size-4"/>Refresh</Button>
        <Button variant="outline" disabled={!report} onClick={() => window.print()}><FileDown className="mr-2 size-4"/>Print / Save PDF</Button>
      </div>
    </div>
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border bg-card p-4 print:border-0 print:p-0">
      <label htmlFor="statement-business-day" className="text-sm font-semibold">Business date</label>
      <input id="statement-business-day" className="h-10 rounded-lg border bg-background px-3 text-sm print:border-0" type="date" value={businessDate} onChange={event => setBusinessDate(event.target.value)} max="9999-12-30"/>
      <span className="text-xs text-muted-foreground">All authorised company branches · LSL</span>
    </div>
    {loading && <p role="status" className="rounded-xl border p-5 text-sm">Loading the live branch ledger...</p>}
    {error && <p role="alert" className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">{error}</p>}
    {report && !loading && <>
      <div className="hidden print:block"><h1 className="text-2xl font-bold">Company-wide Branch Financial Statement</h1><p className="text-sm">Business date: {report.business_date} · Currency: {report.currency}</p></div>
      <section aria-label="Consolidated financial totals" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Opening balance", report.total_opening_balance],
          ["Money received", report.total_money_in],
          ["Total money out", report.total_money_out],
          ["Expected closing", report.consolidated_closing_balance],
        ].map(([label, amount]) => <div key={String(label)} className="rounded-2xl border bg-card p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="mt-2 break-words text-2xl font-extrabold tabular-nums">{format(Number(amount))}</p>
        </div>)}
      </section>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">Branches included</p><p className="mt-1 text-xl font-bold">{report.branches.length}</p></div>
        <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">Closing count recorded</p><p className="mt-1 text-xl font-bold">{reconciliation.declared} / {report.branches.length}</p></div>
        <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">Closing variance (declared branches)</p><p className="mt-1 text-xl font-bold">{format(reconciliation.variances)}</p></div>
        <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">Branches with pending treasury entries</p><p className="mt-1 text-xl font-bold">{reconciliation.unresolved}</p></div>
      </div>
      <section aria-label="Branch financial breakdown" className="overflow-hidden rounded-2xl border bg-card">
        <div className="border-b p-4"><h2 className="flex items-center gap-2 text-lg font-bold"><Building2 className="size-5"/>Branch-by-branch reconciliation</h2>
          <p className="mt-1 text-xs text-muted-foreground">{reconciliation.uncounted} branches have no declared closing count. A missing count does not mean a zero variance.</p></div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[990px] text-sm">
            <thead className="bg-muted/40 text-left"><tr>{["Branch","Status","Opening","Money in","Money out","Expected closing","Counted closing","Variance","Pending"].map(label => <th key={label} scope="col" className="whitespace-nowrap p-3 text-xs font-semibold">{label}</th>)}</tr></thead>
            <tbody>{report.branches.map(branch => <tr key={branch.branch_id} className="border-t hover:bg-muted/20">
              <td className="p-3 font-semibold">{branch.branch_name}{branch.is_headquarters && <span className="ml-2 text-[10px] text-muted-foreground">HQ</span>}</td>
              <td className="p-3">{String(branch.status).replaceAll("_"," ")}</td>
              <td className="whitespace-nowrap p-3 tabular-nums">{format(branch.opening_balance)}</td>
              <td className="whitespace-nowrap p-3 tabular-nums">{format(branch.total_money_in)}</td>
              <td className="whitespace-nowrap p-3 tabular-nums">{format(branch.total_money_out)}</td>
              <td className="whitespace-nowrap p-3 font-bold tabular-nums">{format(branch.expected_closing_balance)}</td>
              <td className="whitespace-nowrap p-3 tabular-nums">{branch.declared_closing_balance === null ? "Not counted" : format(branch.declared_closing_balance)}</td>
              <td className="whitespace-nowrap p-3 tabular-nums">{branch.declared_closing_balance === null ? "—" : format(branch.variance_amount)}</td>
              <td className="p-3">{branch.pending_entry_count}</td>
            </tr>)}
              {report.branches.length === 0 && <tr><td colSpan={9} className="p-6 text-center text-muted-foreground">No active branches were returned for this date.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      <section aria-label="Payment channel reconciliation" className="rounded-2xl border bg-card p-4">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-bold"><ShieldCheck className="size-5"/>Balance by payment channel</h2>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {report.method_totals.map(channel => <div key={channel.method} className="rounded-xl border p-3">
            <p className="text-sm font-bold">{String(channel.method).replaceAll("_", " ")}</p>
            <p className="mt-1 text-lg font-bold tabular-nums">{format(channel.closing_balance)}</p>
            <p className="text-xs text-muted-foreground">Opening {format(channel.opening_balance)} · In {format(channel.money_in)} · Out {format(channel.money_out)}</p>
          </div>)}
        </div>
      </section>
      <p className="text-xs text-muted-foreground">Source: existing tenant-scoped Treasury dashboard. This is an operational statement, not a bank-certified reconciliation. Internal transfers and channel movement should be reviewed before treating consolidated totals as physical cash. Missing or pending transactions must be resolved separately.</p>
    </>}
  </div>;
}
