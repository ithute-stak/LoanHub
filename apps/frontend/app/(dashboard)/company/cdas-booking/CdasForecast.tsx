"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarRange, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasForecast, CdasForecastConcentration } from "@/types/cdasForecast";

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

function ConcentrationList({ title, items }: { title: string; items: CdasForecastConcentration[] }) {
  return <Card>
    <CardHeader><CardTitle className="text-base">{title}</CardTitle><CardDescription>Book Now plus scheduled in-horizon competitor opportunity value.</CardDescription></CardHeader>
    <CardContent>
      {!items.length ? <div className="py-8 text-center text-sm text-muted-foreground">No forecast opportunities in this group.</div> : <div className="space-y-3">{items.map((item, index) => <div key={`${item.name}-${index}`} className="rounded-lg border p-3">
        <div className="flex items-start justify-between gap-3"><div><div className="font-medium">{item.name}</div><div className="text-xs text-muted-foreground">{item.book_now_count} Book Now • {item.scheduled_count} scheduled</div></div><Badge variant="outline">{money(item.total_opportunity_value)}</Badge></div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs"><div><span className="text-muted-foreground">Book Now:</span> {money(item.book_now_value)}</div><div><span className="text-muted-foreground">Scheduled:</span> {money(item.scheduled_value)}</div></div>
      </div>)}</div>}
    </CardContent>
  </Card>;
}

export function CdasForecastView() {
  const [data, setData] = useState<CdasForecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.getForecast());
    } catch {
      setError("Could not load the CDAS forecast.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const maxMonthValue = useMemo(() => Math.max(0, ...(data?.months.map((item) => item.monthly_deduction_value) || [])), [data]);

  if (!data && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading CDAS forecast…</CardContent></Card>;
  if (!data) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "CDAS forecast could not be loaded."}</CardContent></Card>;

  const summary = data.summary;
  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-lg border bg-muted/40 p-2"><CalendarRange className="h-5 w-5"/></div><div><CardTitle>CDAS Forecast</CardTitle><CardDescription>Deterministic booking-window outlook from each client&apos;s latest archived CDAS profile. This forecasts known competitor deduction windows—not approval, eligibility, loan amount, disbursement or revenue.</CardDescription></div></div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Book Now backlog</div><div className="mt-1 text-xl font-semibold">{money(summary.book_now_value)}</div><div className="text-xs text-muted-foreground">{summary.book_now_count} deduction(s) • {summary.book_now_client_count} client(s)</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Next 3 months</div><div className="mt-1 text-xl font-semibold">{money(summary.next_3_months.monthly_deduction_value)}</div><div className="text-xs text-muted-foreground">{summary.next_3_months.opportunity_count} opportunity(s)</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Next 6 months</div><div className="mt-1 text-xl font-semibold">{money(summary.next_6_months.monthly_deduction_value)}</div><div className="text-xs text-muted-foreground">{summary.next_6_months.opportunity_count} opportunity(s)</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">12-month scheduled</div><div className="mt-1 text-xl font-semibold">{money(summary.next_12_months.monthly_deduction_value)}</div><div className="text-xs text-muted-foreground">{summary.next_12_months.opportunity_count} opportunity(s)</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Quality-excluded</div><div className="mt-1 text-xl font-semibold">{money(summary.excluded_quality_value)}</div><div className="text-xs text-muted-foreground">{summary.excluded_quality_count} deduction(s) not forecast</div></div>
        </div>
        <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2 xl:grid-cols-4">
          <div>As of {dateLabel(data.as_of)} • {data.horizon_months}-month horizon</div>
          <div>Peak month: {summary.peak_month || "None"} • {money(summary.peak_month_value)}</div>
          <div>Unscheduled valid rows: {summary.unscheduled_count} • {money(summary.unscheduled_value)}</div>
          <div>Known beyond horizon: {summary.later_known_count} • {money(summary.later_known_value)}</div>
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle className="text-base">12-month booking-window outlook</CardTitle><CardDescription>Monthly deduction value that becomes operationally bookable in each calendar month. Book Now backlog is shown separately above.</CardDescription></CardHeader>
      <CardContent>
        <div className="space-y-3">{data.months.map((item) => {
          const width = maxMonthValue > 0 ? Math.max(2, (item.monthly_deduction_value / maxMonthValue) * 100) : 0;
          return <div key={item.month} className="rounded-lg border p-3">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"><div className="font-medium">{item.label}</div><div className="text-sm font-semibold">{money(item.monthly_deduction_value)}</div></div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-foreground/70" style={{ width: `${width}%` }}/></div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"><span>{item.opportunity_count} opportunity(s)</span><span>{item.client_count} client(s)</span><span>{item.employer_count} employer(s)</span><span>{item.agency_count} agency/agencies</span></div>
          </div>;
        })}</div>
      </CardContent>
    </Card>

    <div className="grid gap-5 xl:grid-cols-2"><ConcentrationList title="Top employers in forecast" items={data.top_employers}/><ConcentrationList title="Top competitor agencies in forecast" items={data.top_agencies}/></div>

    <Card><CardContent className="py-4 text-xs text-muted-foreground">Forecast exclusions: own-company deductions are not treated as competitor opportunities; inactive deductions are ignored; invalid or excluded CDAS rows are reported separately and cannot create forecast windows. {summary.missing_employer_client_count} latest client profile(s) currently have no employer captured.</CardContent></Card>
  </div>;
}
