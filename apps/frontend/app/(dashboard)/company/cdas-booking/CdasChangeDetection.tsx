"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { GitCompareArrows, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasChangeDetection, CdasChangeEntry } from "@/types/cdasChanges";

const MONEY_FIELDS = new Set([
  "assessed_available_amount",
  "reported_active_monthly_deductions",
  "total_monthly_deductions",
  "own_monthly_deductions",
  "competitor_monthly_deductions",
  "amount_owing",
]);

function money(value: unknown) {
  const amount = Number(value);
  return Number.isFinite(amount)
    ? `M ${amount.toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : String(value ?? "—");
}

function dateTime(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("en-ZA", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function scalar(value: unknown, field?: string) {
  if (value === null || value === undefined || value === "") return "—";
  if (field && MONEY_FIELDS.has(field)) return money(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value).replaceAll("_", " ");
}

function deduction(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return scalar(value);
  const row = value as Record<string, unknown>;
  const parts = [
    row.agency_name,
    row.item_code ? `Item ${row.item_code}` : null,
    row.reference_no ? `Ref ${row.reference_no}` : null,
    row.deduction_amount !== null && row.deduction_amount !== undefined ? money(row.deduction_amount) : null,
    row.status,
    row.expiry_date ? `Expiry ${row.expiry_date}` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" • ") : "—";
}

function ChangeRow({ change }: { change: CdasChangeEntry }) {
  const isDeduction = change.field === "deductions";
  return <div className="rounded-lg border p-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="font-medium">{change.label}</div>
      <Badge variant={change.impact === "MATERIAL" ? "default" : "secondary"}>{change.impact === "MATERIAL" ? "Material" : "Info"}</Badge>
    </div>
    {change.changed_fields?.length ? <div className="mt-1 text-xs text-muted-foreground">Changed: {change.changed_fields.map((value) => value.replaceAll("_", " ")).join(", ")}</div> : null}
    <div className="mt-3 grid gap-2 md:grid-cols-2">
      <div className="rounded-md bg-muted/30 p-2"><div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Before</div><div className="mt-1 break-words text-sm">{isDeduction ? deduction(change.before) : scalar(change.before, change.field)}</div></div>
      <div className="rounded-md bg-muted/30 p-2"><div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">After</div><div className="mt-1 break-words text-sm">{isDeduction ? deduction(change.after) : scalar(change.after, change.field)}</div></div>
    </div>
  </div>;
}

export function CdasChangeDetectionView() {
  const [data, setData] = useState<CdasChangeDetection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"all" | "material">("material");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.getChanges());
    } catch {
      setError("Could not load CDAS change detection.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const items = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    return data.items.filter((item) => {
      if (view === "material" && !item.has_material_changes) return false;
      if (!needle) return true;
      return [item.client_name, item.client_reference, item.employer]
        .some((value) => String(value || "").toLowerCase().includes(needle));
    });
  }, [data, query, view]);

  if (!data && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading CDAS changes…</CardContent></Card>;
  if (!data) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "CDAS changes could not be loaded."}</CardContent></Card>;

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-lg border bg-muted/40 p-2"><GitCompareArrows className="h-5 w-5"/></div><div><CardTitle>CDAS Change Detection</CardTitle><CardDescription>Compare each client&apos;s newest archived CDAS analysis with the immediately previous version. Exact duplicate analyses are already deduplicated in Analysis History, so this view focuses on meaningful version changes.</CardDescription></div></div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Clients compared</div><div className="mt-1 text-xl font-semibold">{data.summary.clients_compared}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Clients with material changes</div><div className="mt-1 text-xl font-semibold">{data.summary.clients_with_material_changes}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Total changes</div><div className="mt-1 text-xl font-semibold">{data.summary.total_changes}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Material changes</div><div className="mt-1 text-xl font-semibold">{data.summary.material_changes}</div></div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input aria-label="Search CDAS changes" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search client, reference or employer" className="h-10 flex-1 rounded-md border bg-background px-3 text-sm"/>
          <div className="flex gap-2"><Button size="sm" variant={view === "material" ? "default" : "outline"} onClick={() => setView("material")}>Material only</Button><Button size="sm" variant={view === "all" ? "default" : "outline"} onClick={() => setView("all")}>All comparisons</Button></div>
        </div>
      </CardContent>
    </Card>

    {!data.summary.clients_compared ? <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">Change detection requires at least two archived CDAS analyses for the same exact client identity.</CardContent></Card> : !items.length ? <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">No comparisons match the current filter.</CardContent></Card> : <div className="space-y-4">{items.map((item) => <Card key={`${item.client_key}-${item.latest_analysis_id}`}>
      <CardHeader><div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><CardTitle className="text-lg">{item.client_name || item.client_reference || "CDAS client"}</CardTitle><CardDescription>{item.client_reference || "No reference"}{item.employer ? ` • ${item.employer}` : ""}</CardDescription></div><div className="flex gap-2"><Badge variant={item.has_material_changes ? "default" : "secondary"}>{item.material_change_count} material</Badge><Badge variant="outline">{item.change_count} total</Badge></div></div></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2"><div>Previous analysis: {dateTime(item.previous_analyzed_at)}</div><div>Latest analysis: {dateTime(item.latest_analyzed_at)}</div></div>
        {!item.changes.length ? <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">No tracked fields changed between these two archived versions.</div> : <div className="space-y-2">{item.changes.map((change, index) => <ChangeRow key={`${change.kind}-${change.field}-${index}`} change={change}/>)}</div>}
      </CardContent>
    </Card>)}</div>}
  </div>;
}
