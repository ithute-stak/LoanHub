"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasEmployerIntelligence, CdasEmployerIntelligenceItem } from "@/types/cdasEmployerIntelligence";

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "No known date";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

function EmployerCard({ item }: { item: CdasEmployerIntelligenceItem }) {
  const decisions = Object.entries(item.decision_counts).sort((a, b) => b[1] - a[1]);
  return <Card>
    <CardHeader className="pb-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div><CardTitle className="text-lg">{item.employer_name}</CardTitle><CardDescription>{item.client_count} client profile{item.client_count === 1 ? "" : "s"} • {item.active_deduction_count} active deduction{item.active_deduction_count === 1 ? "" : "s"}</CardDescription></div>
        <div className="flex flex-wrap gap-2"><Badge variant="outline">Competitor share {item.competitor_share_percent.toFixed(1)}%</Badge>{item.data_quality_client_count > 0 && <Badge variant="secondary">{item.data_quality_client_count} quality-risk client{item.data_quality_client_count === 1 ? "" : "s"}</Badge>}</div>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Competitor monthly value</div><div className="mt-1 font-semibold">{money(item.competitor_monthly_value)}</div><div className="text-xs text-muted-foreground">Active total {money(item.active_monthly_value)}</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Book now opportunity</div><div className="mt-1 font-semibold">{money(item.book_now_value)}</div><div className="text-xs text-muted-foreground">{item.book_now_count} deduction(s)</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Next 90 days</div><div className="mt-1 font-semibold">{money(item.next_90_days_value)}</div><div className="text-xs text-muted-foreground">{item.next_90_days_count} opportunity(s)</div></div>
        <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Available CDAS capacity</div><div className="mt-1 font-semibold">{money(item.available_capacity_total)}</div><div className="text-xs text-muted-foreground">Avg {money(item.average_available_capacity)} across {item.capacity_known_count} known</div></div>
      </div>
      <div className="grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div><div className="text-xs text-muted-foreground">Next 30 days</div><div className="font-medium">{money(item.next_30_days_value)} • {item.next_30_days_count} opportunity(s)</div></div>
        <div><div className="text-xs text-muted-foreground">Earliest competitor booking</div><div className="font-medium">{dateLabel(item.earliest_competitor_booking_date)}</div></div>
        <div><div className="text-xs text-muted-foreground">Average deductions/client</div><div className="font-medium">{money(item.average_monthly_deductions_per_client)}</div></div>
        <div><div className="text-xs text-muted-foreground">Capacity / quality risk</div><div className="font-medium">{item.no_headroom_count} no-headroom • {item.data_quality_client_percent.toFixed(1)}% quality issues</div></div>
      </div>
      <div className="space-y-2">
        <div className="text-xs font-medium text-muted-foreground">Decision mix</div>
        <div className="flex flex-wrap gap-2">{decisions.length ? decisions.map(([decision, count]) => <Badge key={decision} variant="outline">{decision.replaceAll("_", " ")}: {count}</Badge>) : <span className="text-sm text-muted-foreground">No decisions captured</span>}</div>
      </div>
      <div className="space-y-2">
        <div className="text-xs font-medium text-muted-foreground">Top competitor agencies</div>
        <div className="flex flex-wrap gap-2">{item.top_competitor_agencies.length ? item.top_competitor_agencies.map((agency) => <Badge key={agency.agency_name} variant="secondary">{agency.agency_name}: {agency.active_deduction_count}</Badge>) : <span className="text-sm text-muted-foreground">No competitor agencies captured</span>}</div>
      </div>
    </CardContent>
  </Card>;
}

export function CdasEmployerIntelligenceView() {
  const [data, setData] = useState<CdasEmployerIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [opportunitiesOnly, setOpportunitiesOnly] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.getEmployerIntelligence());
    } catch {
      setError("Could not load CDAS employer intelligence.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const visible = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    return data.items.filter((item) => {
      if (opportunitiesOnly && item.book_now_value <= 0 && item.next_90_days_value <= 0) return false;
      return !needle || item.employer_name.toLowerCase().includes(needle) || item.top_competitor_agencies.some((agency) => agency.agency_name.toLowerCase().includes(needle));
    });
  }, [data, query, opportunitiesOnly]);

  if (!data && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading employer intelligence…</CardContent></Card>;
  if (!data) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "Employer intelligence could not be loaded."}</CardContent></Card>;

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-lg border bg-muted/40 p-2"><Building2 className="h-5 w-5"/></div><div><CardTitle>CDAS Employer Intelligence</CardTitle><CardDescription>Employer-level intelligence from each client&apos;s latest archived CDAS profile. This view is aggregate-only and does not return client names or references.</CardDescription></div></div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Employers / clients</div><div className="mt-1 text-xl font-semibold">{data.summary.employer_count} / {data.summary.client_count}</div><div className="text-xs text-muted-foreground">{data.summary.missing_employer_clients} clients missing employer</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Competitor monthly value</div><div className="mt-1 text-xl font-semibold">{money(data.summary.competitor_monthly_value)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Book now</div><div className="mt-1 text-xl font-semibold">{money(data.summary.book_now_value)}</div><div className="text-xs text-muted-foreground">{data.summary.book_now_count} opportunity(s)</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Next 90 days</div><div className="mt-1 text-xl font-semibold">{money(data.summary.next_90_days_value)}</div><div className="text-xs text-muted-foreground">30 days {money(data.summary.next_30_days_value)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Available capacity</div><div className="mt-1 text-xl font-semibold">{money(data.summary.available_capacity_total)}</div><div className="text-xs text-muted-foreground">{data.summary.data_quality_client_count} quality-risk clients</div></div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input aria-label="Search employers" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search employer or competitor agency" className="h-10 flex-1 rounded-md border bg-background px-3 text-sm"/>
          <Button size="sm" variant={opportunitiesOnly ? "default" : "outline"} onClick={() => setOpportunitiesOnly((value) => !value)}>Opportunities only</Button>
        </div>
        <div className="text-xs text-muted-foreground">As of {dateLabel(data.as_of)} • active monthly deductions {money(data.summary.active_monthly_value)}</div>
      </CardContent>
    </Card>

    {!visible.length ? <Card><CardContent className="py-14 text-center text-sm text-muted-foreground">No employers match this view.</CardContent></Card> : visible.map((item) => <EmployerCard key={item.employer_name.toLowerCase()} item={item}/>)}
  </div>;
}
