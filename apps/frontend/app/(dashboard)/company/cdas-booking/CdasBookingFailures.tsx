"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, RotateCcw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasBookingFailureWorkspace } from "@/types/cdasBookingFailures";

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateTime(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("en-ZA", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function CdasBookingFailuresView() {
  const [data, setData] = useState<CdasBookingFailureWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [opportunityId, setOpportunityId] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [details, setDetails] = useState("");
  const [retryEligible, setRetryEligible] = useState(false);
  const [retryAfter, setRetryAfter] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await cdasBookingApi.getBookingFailures();
      setData(result);
      setReasonCode((current) => current || result.reason_options[0]?.value || "other");
      setOpportunityId((current) => current || result.recordable_opportunities[0]?.id || "");
    } catch {
      setError("Could not load CDAS booking failure tracking.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const historyItems = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return data.items;
    return data.items.filter((item) => [
      item.client_name,
      item.client_reference,
      item.opportunity_agency_name,
      item.opportunity_reference_no,
      item.latest_failure?.reason_label,
      item.latest_failure?.reason_details,
    ].some((value) => String(value || "").toLowerCase().includes(needle)));
  }, [data, query]);

  async function recordFailure() {
    if (!opportunityId || !reasonCode) return;
    setSaving(true);
    setError("");
    try {
      await cdasBookingApi.recordBookingFailure(opportunityId, {
        reason_code: reasonCode,
        reason_details: details.trim() || undefined,
        retry_eligible: retryEligible,
        retry_after: retryEligible && retryAfter ? retryAfter : undefined,
      });
      setDetails("");
      setRetryEligible(false);
      setRetryAfter("");
      setOpportunityId("");
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not record this booking failure.");
    } finally {
      setSaving(false);
    }
  }

  async function retryFailure(id: string) {
    setRetryingId(id);
    setError("");
    try {
      await cdasBookingApi.retryFailedBooking(id);
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Could not reopen this failed opportunity.");
    } finally {
      setRetryingId(null);
    }
  }

  if (!data && loading) {
    return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading booking failures…</CardContent></Card>;
  }
  if (!data) {
    return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "Booking failures could not be loaded."}</CardContent></Card>;
  }

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><AlertTriangle className="h-5 w-5"/></div>
            <div>
              <CardTitle>CDAS Booking Failure Tracking</CardTitle>
              <CardDescription>Record why a booking failed, preserve every failed attempt, and reopen only failures that are explicitly retryable.</CardDescription>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Failure attempts</div><div className="mt-1 text-xl font-semibold">{data.summary.failure_attempts}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Currently failed</div><div className="mt-1 text-xl font-semibold">{data.summary.currently_failed}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Retryable</div><div className="mt-1 text-xl font-semibold">{data.summary.retryable}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Retry due now</div><div className="mt-1 text-xl font-semibold">{data.summary.retry_due}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Non-retryable</div><div className="mt-1 text-xl font-semibold">{data.summary.non_retryable}</div></div>
        </div>
        {!!data.reason_counts.length && <div className="flex flex-wrap gap-2">{data.reason_counts.map((reason) => <Badge key={reason.reason_code} variant="outline">{reason.reason_label}: {reason.count}</Badge>)}</div>}
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle>Record a failed booking</CardTitle><CardDescription>Select an active opportunity. Recording the failure moves it to the Failed pipeline stage and stops active booking reminders.</CardDescription></CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-2">
        <label className="space-y-1 text-sm"><span className="font-medium">Opportunity</span><select value={opportunityId} onChange={(event) => setOpportunityId(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3"><option value="">Select opportunity</option>{data.recordable_opportunities.map((item) => <option key={item.id} value={item.id}>{item.client_name || item.client_reference || "CDAS client"} — {money(item.opportunity_deduction_amount)}</option>)}</select></label>
        <label className="space-y-1 text-sm"><span className="font-medium">Failure reason</span><select value={reasonCode} onChange={(event) => setReasonCode(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3">{data.reason_options.map((reason) => <option key={reason.value} value={reason.value}>{reason.label}</option>)}</select></label>
        <label className="space-y-1 text-sm lg:col-span-2"><span className="font-medium">Details</span><textarea value={details} onChange={(event) => setDetails(event.target.value)} maxLength={4000} rows={3} placeholder="What happened, error/reference returned, or action needed…" className="w-full rounded-md border bg-background p-3"/></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={retryEligible} onChange={(event) => { setRetryEligible(event.target.checked); if (!event.target.checked) setRetryAfter(""); }}/><span>Allow this opportunity to be retried</span></label>
        <label className="space-y-1 text-sm"><span className="font-medium">Retry after</span><input type="datetime-local" value={retryAfter} disabled={!retryEligible} onChange={(event) => setRetryAfter(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 disabled:opacity-50"/><span className="text-xs text-muted-foreground">Leave blank for an immediately retryable failure.</span></label>
        <div className="lg:col-span-2"><Button onClick={() => void recordFailure()} disabled={saving || !opportunityId || !reasonCode}>{saving ? "Recording…" : "Record failure"}</Button></div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle>Failure history</CardTitle><CardDescription>Previous failure attempts remain visible even after an opportunity is reopened and later succeeds.</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        <input aria-label="Search booking failures" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search client, agency, reference or failure reason" className="h-10 w-full rounded-md border bg-background px-3 text-sm sm:max-w-lg"/>
        {!historyItems.length ? <div className="py-10 text-center text-sm text-muted-foreground">No booking failures have been recorded yet.</div> : <div className="grid gap-4 lg:grid-cols-2">{historyItems.map((item) => {
          const latest = item.latest_failure;
          const failedNow = item.pipeline_stage === "failed";
          return <Card key={item.id} className={failedNow ? "border-amber-500/40" : ""}>
            <CardHeader className="pb-3"><div className="flex items-start justify-between gap-3"><div><CardTitle className="text-base">{item.client_name || item.client_reference || "CDAS client"}</CardTitle><CardDescription>{item.opportunity_agency_name || "Agency not captured"} • {money(item.opportunity_deduction_amount)}</CardDescription></div><Badge variant={failedNow ? "outline" : "secondary"}>{failedNow ? "Failed" : item.pipeline_stage.replaceAll("_", " ")}</Badge></div></CardHeader>
            <CardContent className="space-y-3 text-sm">
              {latest && <div className="rounded-lg border p-3"><div className="font-medium">{latest.reason_label}</div><div className="mt-1 text-xs text-muted-foreground">Failed {dateTime(latest.failed_at)}</div>{latest.reason_details && <p className="mt-2 text-sm">{latest.reason_details}</p>}<div className="mt-2 text-xs text-muted-foreground">{latest.retry_eligible ? `Retry ${latest.retry_after ? `after ${dateTime(latest.retry_after)}` : "allowed immediately"}` : "Not retryable"}</div></div>}
              <div className="flex items-center justify-between gap-3"><span className="text-xs text-muted-foreground">{item.failure_count} recorded failure attempt{item.failure_count === 1 ? "" : "s"}</span>{failedNow && latest?.retry_eligible && <Button size="sm" variant={item.retry_due ? "default" : "outline"} disabled={!item.retry_due || retryingId === item.id} onClick={() => void retryFailure(item.id)}><RotateCcw className="mr-2 h-4 w-4"/>{item.retry_due ? (retryingId === item.id ? "Reopening…" : "Reopen for retry") : "Retry not due"}</Button>}</div>
              {item.failure_history.length > 1 && <details><summary className="cursor-pointer text-xs font-medium">View earlier failures</summary><div className="mt-2 space-y-2">{item.failure_history.slice(1).map((failure) => <div key={failure.id} className="rounded border p-2 text-xs"><div className="font-medium">{failure.reason_label}</div><div className="text-muted-foreground">{dateTime(failure.failed_at)}</div></div>)}</div></details>}
            </CardContent>
          </Card>;
        })}</div>}
      </CardContent>
    </Card>
  </div>;
}
