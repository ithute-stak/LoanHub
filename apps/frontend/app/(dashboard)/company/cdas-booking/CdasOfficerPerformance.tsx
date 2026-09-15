"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, UsersRound } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { CdasOfficerPerformanceWorkspace } from "@/types/cdasOfficerPerformance";

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function labelize(value?: string | null) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function CdasOfficerPerformanceView() {
  const [data, setData] = useState<CdasOfficerPerformanceWorkspace | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.getOfficerPerformance());
    } catch {
      setError("Could not load CDAS officer assignment and performance.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const visibleOfficers = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return data.officers;
    return data.officers.filter((item) => [item.name, item.email, item.phone, item.role].some((value) => String(value || "").toLowerCase().includes(needle)));
  }, [data, query]);

  const activeStaff = useMemo(() => data?.officers.filter((item) => item.is_active) || [], [data]);

  async function assign(opportunityId: string, userId: string) {
    if (!userId) return;
    setSavingId(opportunityId);
    setError("");
    try {
      await cdasBookingApi.assignOpportunity(opportunityId, userId);
      await refresh();
    } catch (error: any) {
      setError(error?.response?.data?.detail || "Could not assign this opportunity.");
    } finally {
      setSavingId("");
    }
  }

  if (!data && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading officer assignment and performance…</CardContent></Card>;
  if (!data) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "Officer performance could not be loaded."}</CardContent></Card>;

  const summary = data.summary;
  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-lg border bg-muted/40 p-2"><UsersRound className="h-5 w-5"/></div><div><CardTitle>CDAS Officer Assignment & Performance</CardTitle><CardDescription>Transparent operational workload and activity by officer. No composite staff score, borrower approval metric or credit-quality ranking is used.</CardDescription></div></div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Active staff</div><div className="mt-1 text-xl font-semibold">{summary.active_staff}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Assigned open</div><div className="mt-1 text-xl font-semibold">{summary.assigned_open}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Unassigned open</div><div className="mt-1 text-xl font-semibold">{summary.unassigned_open}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Book Now open</div><div className="mt-1 text-xl font-semibold">{summary.book_now_open}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Overdue follow-ups</div><div className="mt-1 text-xl font-semibold">{summary.overdue_follow_ups}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Contacts · 30 days</div><div className="mt-1 text-xl font-semibold">{summary.contacts_last_30_days}</div></div>
        </div>
        <div className="text-xs text-muted-foreground">Recorded workflow outcomes: {summary.booked_total} booked • {summary.failed_total} failed. These counts describe CDAS workflow state; they are not staff approval or credit-quality scores.</div>
        <Input aria-label="Search officers" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search officer, role, email or phone" className="sm:max-w-md"/>
      </CardContent>
    </Card>

    <div className="grid gap-4 xl:grid-cols-2">
      {visibleOfficers.map((officer) => <Card key={officer.user_id}>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle className="text-base">{officer.name}</CardTitle><CardDescription>{officer.role || "Company staff"}{officer.email ? ` • ${officer.email}` : ""}</CardDescription></div><Badge variant={officer.is_active ? "secondary" : "outline"}>{officer.is_active ? "Active" : "Inactive"}</Badge></div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Open workload</div><div className="text-lg font-semibold">{officer.open_assigned}</div><div className="text-xs text-muted-foreground">{money(officer.open_monthly_deduction_value)}</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Book Now</div><div className="text-lg font-semibold">{officer.book_now_assigned}</div><div className="text-xs text-muted-foreground">{officer.upcoming_assigned} upcoming</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Contacts · 30 days</div><div className="text-lg font-semibold">{officer.contacts_last_30_days}</div><div className="text-xs text-muted-foreground">{officer.contacts_total} all time</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Follow-up attention</div><div className="text-lg font-semibold">{officer.overdue_follow_ups}</div><div className="text-xs text-muted-foreground">overdue • {officer.scheduled_follow_ups} scheduled</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Uncontacted open</div><div className="text-lg font-semibold">{officer.uncontacted_open}</div><div className="text-xs text-muted-foreground">current assignment</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Current outcomes</div><div className="text-lg font-semibold">{officer.booked_assigned} / {officer.failed_assigned}</div><div className="text-xs text-muted-foreground">booked / failed assignments</div></div>
          </div>
          <div className="grid gap-3 text-xs sm:grid-cols-2">
            <div className="rounded-lg bg-muted/30 p-3"><div className="font-medium">Activity attribution</div><div className="mt-1 text-muted-foreground">{officer.booked_by_officer} booking action(s) recorded by this officer • {officer.failures_reported_last_30_days} failure report(s) in the last 30 days.</div></div>
            <div className="rounded-lg bg-muted/30 p-3"><div className="font-medium">Recent contact outcomes</div><div className="mt-1 text-muted-foreground">{Object.entries(officer.contact_outcomes_last_30_days).length ? Object.entries(officer.contact_outcomes_last_30_days).map(([key, value]) => `${labelize(key)} ${value}`).join(" • ") : "No contacts recorded in this window."}</div></div>
          </div>
        </CardContent>
      </Card>)}
      {!visibleOfficers.length && <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground xl:col-span-2">No officers match this search.</div>}
    </div>

    <Card>
      <CardHeader><CardTitle className="text-base">Unassigned CDAS opportunities</CardTitle><CardDescription>Distribute current open work to active company staff. The existing company-membership validation still applies to every assignment.</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        {!data.unassigned_items.length && <div className="py-8 text-center text-sm text-muted-foreground">All current CDAS opportunities are assigned.</div>}
        {data.unassigned_items.map((item) => <div key={item.id} className="grid gap-3 rounded-lg border p-4 lg:grid-cols-[minmax(0,1fr)_160px_280px] lg:items-center">
          <div><div className="font-medium">{item.client_name || item.client_reference || "CDAS client"}</div><div className="text-xs text-muted-foreground">{item.opportunity_agency_name || "Agency not captured"} • {labelize(item.pipeline_stage)} • {item.booking_open_date || "No booking date"}</div></div>
          <div><Badge variant={item.state === "BOOK_NOW" ? "secondary" : "outline"}>{labelize(item.state)}</Badge><div className="mt-1 text-sm font-medium">{money(item.opportunity_deduction_amount)}</div></div>
          <select aria-label={`Assign ${item.client_name || item.client_reference || "opportunity"}`} defaultValue="" disabled={savingId === item.id || !activeStaff.length} onChange={(event) => void assign(item.id, event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="">Assign to officer…</option>{activeStaff.map((officer) => <option key={officer.user_id} value={officer.user_id}>{officer.name} — {officer.open_assigned} open</option>)}</select>
        </div>)}
      </CardContent>
    </Card>
  </div>;
}
