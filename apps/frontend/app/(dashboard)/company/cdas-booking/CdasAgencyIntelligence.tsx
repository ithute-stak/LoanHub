"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasAgencyIntelligence, CdasAgencyIntelligenceItem } from "@/types/cdasAgencyIntelligence";

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "No known date";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

function AgencyCard({ item }: { item: CdasAgencyIntelligenceItem }) {
  return <Card>
    <CardHeader className="pb-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div><CardTitle className="text-base">{item.agency_name}</CardTitle><CardDescription>{item.client_count} client profile{item.client_count === 1 ? "" : "s"} • {item.active_deduction_count} active deduction{item.active_deduction_count === 1 ? "" : "s"}</CardDescription></div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">Competitor share {item.competitor_value_share_percent.toFixed(1)}%</Badge>
          {item.data_quality_issue_count > 0 && <Badge variant="secondary">{item.data_quality_issue_count} quality issue{item.data_quality_issue_count === 1 ? "" : "s"}</Badge>}
        </div>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Competitor monthly value</div><div className="mt-1 font-semibold">{money(item.competitor_monthly_value)}</div><div className="text-xs text-muted-foreground">{item.competitor_booking_count} deduction(s)</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Own monthly value</div><div className="mt-1 font-semibold">{money(item.own_monthly_value)}</div><div className="text-xs text-muted-foreground">{item.own_booking_count} deduction(s)</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Book now opportunity</div><div className="mt-1 font-semibold">{money(item.book_now_value)}</div><div className="text-xs text-muted-foreground">{item.book_now_count} deduction(s)</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Average deduction</div><div className="mt-1 font-semibold">{money(item.average_deduction_amount)}</div><div className="text-xs text-muted-foreground">Active total {money(item.active_monthly_value)}</div></div>
      </div>
      <div className="grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div><div className="text-xs text-muted-foreground">Next 30 days</div><div className="font-medium">{money(item.next_30_days_value)} • {item.next_30_days_count} opportunity(s)</div></div>
        <div><div className="text-xs text-muted-foreground">Next 90 days</div><div className="font-medium">{money(item.next_90_days_value)} • {item.next_90_days_count} opportunity(s)</div></div>
        <div><div className="text-xs text-muted-foreground">Earliest competitor booking</div><div className="font-medium">{dateLabel(item.earliest_competitor_booking_date)}</div></div>
        <div><div className="text-xs text-muted-foreground">Item codes</div><div className="font-medium">{item.item_codes.length ? item.item_codes.join(", ") : "None captured"}</div></div>
      </div>
    </CardContent>
  </Card>;
}

export function CdasAgencyIntelligenceView() {
  const [data, setData] = useState<CdasAgencyIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.getAgencyIntelligence());
    } catch {
      setError("Could not load CDAS agency intelligence.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const visible = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return data.items;
    return data.items.filter((item) => item.agency_name.toLowerCase().includes(needle) || item.item_codes.some((code) => code.toLowerCase().includes(needle)));
  }, [data, query]);

  if (!data && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading agency intelligence…</CardContent></Card>;
  if (!data) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "Agency intelligence could not be loaded."}</CardContent></Card>;

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-lg border bg-muted/40 p-2"><Building2 className="h-5 w-5"/></div><div><CardTitle>CDAS Agency Intelligence</CardTitle><CardDescription>Agency-level intelligence from each client&apos;s latest archived CDAS analysis. Historical versions remain in Analysis History but are not double-counted here.</CardDescription></div></div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Competitor monthly value</div><div className="mt-1 text-xl font-semibold">{money(data.summary.competitor_monthly_value)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Book now</div><div className="mt-1 text-xl font-semibold">{money(data.summary.book_now_value)}</div><div className="text-xs text-muted-foreground">{data.summary.book_now_count} opportunity(s)</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Next 30 days</div><div className="mt-1 text-xl font-semibold">{money(data.summary.next_30_days_value)}</div><div className="text-xs text-muted-foreground">{data.summary.next_30_days_count} opportunity(s)</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Next 90 days</div><div className="mt-1 text-xl font-semibold">{money(data.summary.next_90_days_value)}</div><div className="text-xs text-muted-foreground">{data.summary.next_90_days_count} opportunity(s)</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Agencies / clients</div><div className="mt-1 text-xl font-semibold">{data.summary.agency_count} / {data.summary.client_count}</div></div>
        </div>
        <input aria-label="Search agencies" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search agency or item code" className="h-10 w-full rounded-md border bg-background px-3 text-sm sm:max-w-md"/>
        <div className="text-xs text-muted-foreground">As of {dateLabel(data.as_of)} • active monthly deductions {money(data.summary.active_monthly_value)} • own monthly value {money(data.summary.own_monthly_value)}</div>
      </CardContent>
    </Card>

    {!visible.length ? <Card><CardContent className="py-14 text-center text-sm text-muted-foreground">No agencies match this view.</CardContent></Card> : visible.map((item) => <AgencyCard key={item.agency_name.toLowerCase()} item={item}/>)}
  </div>;
}
