"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, RefreshCcw, AlertTriangle, Activity } from "lucide-react";

import { getFolioPerformance, type FolioPerformance, type FolioPerformanceMetrics } from "@/api/folioBook";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageLoader } from "@/components/ui/page-loader";
import { toast } from "@/utils/toast";

const money = (value: number) => new Intl.NumberFormat("en-LS", {
  style: "currency", currency: "LSL", minimumFractionDigits: 2, maximumFractionDigits: 2,
}).format(value || 0);

function Metric({ label, amount, hint }: { label: string; amount: string; hint?: string }) {
  return <Card className="h-full">
    <CardContent className="space-y-1 p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="break-words text-xl font-black tabular-nums sm:text-2xl">{amount}</p>
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </CardContent>
  </Card>;
}

function GroupCard({ name, data, notes }: {
  name: string;
  data: FolioPerformanceMetrics;
  notes: FolioPerformance["definitions"];
}) {
  return <Card className="overflow-hidden">
    <CardHeader className="border-b bg-muted/20">
      <CardTitle className="text-xl">{name}</CardTitle>
      <CardDescription>{data.loan_count} loans · {data.active_loans} active</CardDescription>
    </CardHeader>
    <CardContent className="space-y-3 p-5">
      <div className="flex justify-between gap-3 text-sm"><span className="text-muted-foreground">Outstanding balance</span><strong className="tabular-nums">{money(data.outstanding_balance)}</strong></div>
      <div className="flex justify-between gap-3 text-sm"><span className="text-muted-foreground">Scheduled this month</span><strong className="tabular-nums">{money(data.month_scheduled)}</strong></div>
      <div className="flex justify-between gap-3 text-sm"><span className="text-muted-foreground">Unpaid this month</span><strong className="tabular-nums">{money(data.month_unpaid)}</strong></div>
      <div className="flex justify-between gap-3 text-sm"><span className="text-muted-foreground">Overdue instalments</span><strong className="tabular-nums">{money(data.overdue_instalments)}</strong></div>
      <div className="flex justify-between gap-3 text-sm"><span className="text-muted-foreground">Recorded collections</span><strong className="tabular-nums">{money(data.recorded_month_collections)}</strong></div>
      <div className="flex justify-between gap-3 text-sm"><span className="text-muted-foreground">Overdue loans (flagged)</span><strong>{data.overdue_loans}</strong></div>
      <p className="border-t pt-3 text-xs text-muted-foreground">{notes.recorded_month_collections}</p>
    </CardContent>
  </Card>;
}

export default function FolioPerformancePage() {
  const [data, setData] = useState<FolioPerformance | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await getFolioPerformance());
    } catch (error) {
      toast.error(error, { description: "Could not load folio performance." });
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (!data && loading) return <PageLoader rows={6} />;
  return <div className="loanhub-page space-y-6 pb-12">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <Link className="mb-3 inline-flex items-center gap-1 text-sm text-primary hover:underline" href="/company/folio-book"><ArrowLeft className="h-4 w-4"/> Folio Book</Link>
        <h1 className="flex items-center gap-2 text-3xl font-black"><Activity className="h-7 w-7"/> Folio Performance</h1>
        {data ? <p className="mt-2 text-sm text-muted-foreground">As of {data.as_of} · Month {data.month} · {data.scope} scope · LSL</p> : null}
      </div>
      <Button variant="outline" disabled={loading} onClick={() => void load()}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/> Refresh</Button>
    </div>
    {!data ? <div role="alert" className="rounded-xl border p-5 text-sm"><AlertTriangle className="mr-2 inline h-4 w-4"/> Dashboard data unavailable. Retry refresh.</div> : <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Registered loans" amount={String(data.totals.loan_count)} hint={`${data.totals.active_loans} active loans`}/>
        <Metric label="Outstanding balance" amount={money(data.totals.outstanding_balance)} hint={data.definitions.outstanding_balance}/>
        <Metric label="Scheduled this month" amount={money(data.totals.month_scheduled)} hint={data.definitions.month_scheduled}/>
        <Metric label="Recorded collections" amount={money(data.totals.recorded_month_collections)} hint="Successful repayment transactions this month"/>
        <Metric label="Unpaid this month" amount={money(data.totals.month_unpaid)} hint={data.definitions.month_unpaid}/>
        <Metric label="Overdue instalments" amount={money(data.totals.overdue_instalments)} hint={data.definitions.overdue_instalments}/>
        <Metric label="Overdue loan flags" amount={String(data.totals.overdue_loans)} hint="Outstanding loans flagged overdue"/>
        <Metric label="Lifetime loan payments" amount={money(data.totals.lifetime_paid)} hint="Loan-level cumulative payment total"/>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {data.groups.map(group => <GroupCard key={group.group_code} name={group.group_code} data={group} notes={data.definitions}/>)}
      </div>
      <p className="text-xs text-muted-foreground">Amounts are operational snapshots, not an accounting trial balance. Scheduled instalments and recorded collections have different definitions and must not be netted as if they were the same ledger.</p>
    </>}
  </div>;
}
