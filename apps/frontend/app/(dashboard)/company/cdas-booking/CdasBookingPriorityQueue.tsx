"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CalendarClock, CheckCircle2, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasBookingPriorityBand, CdasBookingPriorityItem, CdasBookingPriorityQueue } from "@/types/cdasBookingPriority";

type PriorityView = "attention" | "critical" | "high" | "medium" | "low" | "booked" | "all";

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "No date";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

function bandClass(band: CdasBookingPriorityBand) {
  if (band === "CRITICAL") return "border-red-500 text-red-700 dark:text-red-300";
  if (band === "HIGH") return "border-amber-500 text-amber-700 dark:text-amber-300";
  if (band === "MEDIUM") return "border-blue-500 text-blue-700 dark:text-blue-300";
  if (band === "BOOKED") return "border-emerald-500 text-emerald-700 dark:text-emerald-300";
  return "";
}

function matchesView(item: CdasBookingPriorityItem, view: PriorityView) {
  if (view === "all") return true;
  if (view === "attention") return item.priority_band !== "BOOKED";
  if (view === "booked") return item.priority_band === "BOOKED";
  return item.priority_band === view.toUpperCase();
}

function PriorityCard({ item, busy, onBooked }: { item: CdasBookingPriorityItem; busy: boolean; onBooked: (id: string) => void }) {
  const due = item.days_from_today !== null && item.days_from_today <= 0;
  return <Card className={item.priority_band === "CRITICAL" ? "border-red-500/40" : item.priority_band === "HIGH" ? "border-amber-500/40" : ""}>
    <CardHeader className="pb-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-lg">{item.client_name || item.client_reference || "CDAS client"}</CardTitle>
            <Badge variant="outline" className={bandClass(item.priority_band)}>{item.priority_band}</Badge>
          </div>
          <CardDescription className="mt-1">{item.agency_name || "Agency not captured"}{item.reference_no ? ` • ${item.reference_no}` : ""}</CardDescription>
        </div>
        <div className="min-w-24 rounded-xl border bg-muted/20 px-4 py-3 text-center">
          <div className="text-3xl font-bold leading-none">{item.priority_score}</div>
          <div className="mt-1 text-xs text-muted-foreground">priority / 100</div>
        </div>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Booking date</div><div className="font-semibold">{dateLabel(item.booking_date)}</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Monthly deduction</div><div className="font-semibold">{money(item.deduction_amount)}</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Available capacity</div><div className="font-semibold">{item.assessed_available_amount === null ? "Unknown" : money(item.assessed_available_amount)}</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Amount owing</div><div className="font-semibold">{item.amount_owing === null ? "Not supplied" : money(item.amount_owing)}</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Suggested term</div><div className="font-semibold">{item.booking_months ? `${item.booking_months} month(s)` : "—"}</div></div>
      </div>

      <div>
        <div className="mb-2 text-sm font-medium">Score breakdown</div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg bg-muted/40 p-3"><div className="text-xs text-muted-foreground">Timing urgency</div><div className="font-semibold">{item.priority_components.urgency} / 50</div></div>
          <div className="rounded-lg bg-muted/40 p-3"><div className="text-xs text-muted-foreground">Opportunity value</div><div className="font-semibold">{item.priority_components.value} / 20</div></div>
          <div className="rounded-lg bg-muted/40 p-3"><div className="text-xs text-muted-foreground">Booking readiness</div><div className="font-semibold">{item.priority_components.readiness} / 20</div></div>
          <div className="rounded-lg bg-muted/40 p-3"><div className="text-xs text-muted-foreground">Data quality</div><div className="font-semibold">{item.priority_components.quality} / 10</div></div>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-2">
        {item.priority_reasons.map((reason) => <div key={reason} className="flex items-start gap-2 text-sm"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"/><span>{reason}</span></div>)}
      </div>

      {item.priority_warnings.length > 0 && <div className="rounded-lg border border-amber-500/50 bg-amber-50/50 p-3 dark:bg-amber-950/20">
        <div className="flex items-center gap-2 text-sm font-medium text-amber-800 dark:text-amber-200"><AlertTriangle className="h-4 w-4"/>Needs attention</div>
        <div className="mt-2 space-y-1 text-sm text-amber-800/90 dark:text-amber-200/90">{item.priority_warnings.map((warning) => <div key={warning}>{warning}</div>)}</div>
      </div>}

      {item.priority_band !== "BOOKED" && (item.state === "BOOK_NOW" || due) && <Button disabled={busy} onClick={() => onBooked(item.id)}><CheckCircle2 className="mr-2 h-4 w-4"/>{busy ? "Updating..." : "Mark booking complete"}</Button>}
    </CardContent>
  </Card>;
}

export function CdasBookingPriorityQueueView() {
  const [queue, setQueue] = useState<CdasBookingPriorityQueue | null>(null);
  const [view, setView] = useState<PriorityView>("attention");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setQueue(await cdasBookingApi.getBookingPriorities());
    } catch {
      setError("Could not load the CDAS booking priority queue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function markBooked(id: string) {
    setBusyId(id);
    setError("");
    try {
      await cdasBookingApi.markBooked(id);
      await refresh();
    } catch {
      setError("Could not mark this booking complete.");
    } finally {
      setBusyId(null);
    }
  }

  const visible = useMemo(() => queue ? queue.items.filter((item) => matchesView(item, view)) : [], [queue, view]);

  if (!queue && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Calculating booking priorities…</CardContent></Card>;
  if (!queue) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "The priority queue could not be loaded."}</CardContent></Card>;

  const filters: Array<{ id: PriorityView; label: string; count: number }> = [
    { id: "attention", label: "Needs Attention", count: queue.summary.open },
    { id: "critical", label: "Critical", count: queue.summary.critical },
    { id: "high", label: "High", count: queue.summary.high },
    { id: "medium", label: "Medium", count: queue.summary.medium },
    { id: "low", label: "Low", count: queue.summary.low },
    { id: "booked", label: "Booked", count: queue.summary.booked },
    { id: "all", label: "All", count: queue.total },
  ];

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><CalendarClock className="h-5 w-5"/></div>
            <div><CardTitle>CDAS Booking Priority Queue</CardTitle><CardDescription>Explainable 0–100 ranking based on timing, deduction value, booking readiness and CDAS data quality. Highest-priority open opportunities appear first.</CardDescription></div>
          </div>
          <Button variant="outline" size="sm" disabled={loading} onClick={() => void refresh()}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <button type="button" onClick={() => setView("critical")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="text-xs text-muted-foreground">Critical</div><div className="mt-1 text-2xl font-semibold">{queue.summary.critical}</div></button>
          <button type="button" onClick={() => setView("high")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="text-xs text-muted-foreground">High priority</div><div className="mt-1 text-2xl font-semibold">{queue.summary.high}</div></button>
          <button type="button" onClick={() => setView("medium")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="text-xs text-muted-foreground">Medium</div><div className="mt-1 text-2xl font-semibold">{queue.summary.medium}</div></button>
          <button type="button" onClick={() => setView("low")} className="rounded-lg border p-3 text-left transition hover:bg-muted/40"><div className="text-xs text-muted-foreground">Low</div><div className="mt-1 text-2xl font-semibold">{queue.summary.low}</div></button>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Open monthly value</div><div className="mt-1 text-xl font-semibold">{money(queue.summary.monthly_deduction_value)}</div></div>
        </div>
        <div className="flex flex-wrap gap-2">{filters.map((filter) => <Button key={filter.id} size="sm" variant={view === filter.id ? "default" : "outline"} onClick={() => setView(filter.id)}>{filter.label}<Badge variant="secondary" className="ml-2">{filter.count}</Badge></Button>)}</div>
        <div className="text-xs text-muted-foreground">As of {dateLabel(queue.as_of)} • {queue.summary.review_required} record(s) require CDAS review</div>
      </CardContent>
    </Card>

    {!visible.length ? <Card><CardContent className="py-14 text-center text-sm text-muted-foreground">No booking opportunities match this priority view.</CardContent></Card> : <div className="space-y-4">{visible.map((item) => <PriorityCard key={item.id} item={item} busy={busyId === item.id} onBooked={(id) => void markBooked(id)}/>)}</div>}
  </div>;
}
