"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FileClock, LockKeyhole, RefreshCw, Search, ShieldCheck, TriangleAlert } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { CdasAuditEvent, CdasAuditTrailResponse } from "@/types/cdasAuditTrail";

function dateTimeLabel(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("en-ZA", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function actionLabel(value: string) {
  return value.replace(/^CDAS_/, "").replaceAll("_", " ");
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function changedRows(event: CdasAuditEvent) {
  const keys = event.changed_fields.length
    ? event.changed_fields
    : Array.from(new Set([...Object.keys(event.before_data), ...Object.keys(event.after_data)]));
  return keys.filter((key) => key !== "analysis_snapshot" && key !== "notes" && key !== "reason_details");
}

export default function CdasAuditTrail() {
  const [data, setData] = useState<CdasAuditTrailResponse | null>(null);
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [actor, setActor] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await cdasBookingApi.getAuditTrail({
        search: search.trim() || undefined,
        action: action || undefined,
        entity_type: entityType || undefined,
        actor_user_id: actor || undefined,
        date_from: dateFrom ? `${dateFrom}T00:00:00` : undefined,
        date_to: dateTo ? `${dateTo}T23:59:59` : undefined,
        page,
        page_size: 50,
      });
      setData(result);
    } catch {
      setError("Unable to load the formal CDAS audit trail. This workspace requires a company transparency role.");
    } finally {
      setLoading(false);
    }
  }, [action, actor, dateFrom, dateTo, entityType, page, search]);

  useEffect(() => { void load(); }, [load]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil((data?.total || 0) / (data?.page_size || 50))),
    [data],
  );

  function clearFilters() {
    setSearch("");
    setAction("");
    setEntityType("");
    setActor("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  }

  return <div className="space-y-5">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <div className="flex items-center gap-2">
          <FileClock className="h-6 w-6" />
          <h1 className="text-2xl font-semibold tracking-tight">Formal CDAS Audit Trail</h1>
        </div>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Append-only business events for CDAS analyses and workflow changes. Events are company-scoped and hash-sealed by LoanHub&apos;s audit integrity layer.
        </p>
      </div>
      <Button variant="outline" onClick={() => void load()} disabled={loading}>
        <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
      </Button>
    </div>

    <Alert>
      <LockKeyhole className="h-4 w-4" />
      <AlertTitle>Read-only integrity record</AlertTitle>
      <AlertDescription>
        Audit events cannot be edited or deleted after sealing. Raw pasted CDAS text, full analysis snapshots, contact notes and free-form failure details are excluded from this formal trail.
      </AlertDescription>
    </Alert>

    {error && <Alert variant="destructive"><TriangleAlert className="h-4 w-4"/><AlertTitle>Audit trail unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}

    <div className="grid gap-3 sm:grid-cols-3">
      <Card><CardHeader className="pb-2"><CardDescription>Formal events sampled</CardDescription><CardTitle>{data?.summary.formal_events_sampled ?? 0}</CardTitle></CardHeader></Card>
      <Card><CardHeader className="pb-2"><CardDescription>Hash sealed</CardDescription><CardTitle>{data?.summary.sealed_events_sampled ?? 0}</CardTitle></CardHeader></Card>
      <Card><CardHeader className="pb-2"><CardDescription>Unsealed formal events</CardDescription><CardTitle>{data?.summary.unsealed_events_sampled ?? 0}</CardTitle></CardHeader></Card>
    </div>

    <Card>
      <CardHeader>
        <CardTitle className="text-base">Search and filters</CardTitle>
        <CardDescription>Filter by actor, action, record type or date without changing the underlying evidence.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <label className="relative xl:col-span-3">
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search action description, record type or role" className="pl-9" />
        </label>
        <select value={action} onChange={(event) => { setAction(event.target.value); setPage(1); }} className="h-10 rounded-md border bg-background px-3 text-sm">
          <option value="">All actions</option>
          {(data?.options.actions || []).map((value) => <option key={value} value={value}>{actionLabel(value)}</option>)}
        </select>
        <select value={entityType} onChange={(event) => { setEntityType(event.target.value); setPage(1); }} className="h-10 rounded-md border bg-background px-3 text-sm">
          <option value="">All record types</option>
          {(data?.options.entity_types || []).map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}
        </select>
        <select value={actor} onChange={(event) => { setActor(event.target.value); setPage(1); }} className="h-10 rounded-md border bg-background px-3 text-sm">
          <option value="">All actors</option>
          {(data?.options.actors || []).map((value) => <option key={value.user_id} value={value.user_id}>{value.name}{value.role ? ` · ${value.role}` : ""}</option>)}
        </select>
        <label className="space-y-1 text-xs text-muted-foreground">From<Input type="date" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); setPage(1); }} /></label>
        <label className="space-y-1 text-xs text-muted-foreground">To<Input type="date" value={dateTo} onChange={(event) => { setDateTo(event.target.value); setPage(1); }} /></label>
        <div className="flex items-end"><Button variant="ghost" onClick={clearFilters}>Clear filters</Button></div>
      </CardContent>
    </Card>

    <div className="space-y-3">
      {(data?.items || []).map((event) => {
        const fields = changedRows(event);
        return <Card key={event.id}>
          <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={event.severity === "warning" ? "destructive" : "secondary"}>{actionLabel(event.action)}</Badge>
                <Badge variant="outline">{event.entity_type?.replaceAll("_", " ") || "CDAS event"}</Badge>
                {event.integrity.sealed
                  ? <Badge variant="outline" className="gap-1"><ShieldCheck className="h-3 w-3"/>SEALED</Badge>
                  : <Badge variant="destructive">UNSEALED</Badge>}
              </div>
              <CardTitle className="mt-2 text-base">{event.description || actionLabel(event.action)}</CardTitle>
              <CardDescription>
                {event.actor_name || "System / unknown actor"}{event.actor_role ? ` · ${event.actor_role}` : ""} · {dateTimeLabel(event.timestamp)}
              </CardDescription>
            </div>
            <div className="text-right text-xs text-muted-foreground">
              <div>Record {event.record_id ? event.record_id.slice(0, 8) : "—"}</div>
              <div>Request {event.request_id ? event.request_id.slice(0, 12) : "—"}</div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {fields.length > 0 && <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-left text-xs text-muted-foreground"><tr><th className="px-3 py-2">Field</th><th className="px-3 py-2">Before</th><th className="px-3 py-2">After</th></tr></thead>
                <tbody>{fields.map((field) => <tr key={field} className="border-t"><td className="px-3 py-2 font-medium">{field.replaceAll("_", " ")}</td><td className="px-3 py-2 text-muted-foreground">{displayValue(event.before_data[field])}</td><td className="px-3 py-2">{displayValue(event.after_data[field])}</td></tr>)}</tbody>
              </table>
            </div>}
            <div className="grid gap-2 rounded-md bg-muted/30 p-3 text-xs text-muted-foreground md:grid-cols-3">
              <div><span className="font-medium text-foreground">Hash version:</span> {event.integrity.hash_version || "—"}</div>
              <div><span className="font-medium text-foreground">Sealed:</span> {dateTimeLabel(event.integrity.sealed_at)}</div>
              <div className="truncate font-mono" title={event.integrity.event_hash || ""}><span className="font-sans font-medium text-foreground">Event hash:</span> {event.integrity.event_hash || "—"}</div>
            </div>
          </CardContent>
        </Card>;
      })}
      {!loading && data && data.items.length === 0 && <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No formal CDAS audit events match these filters.</CardContent></Card>}
    </div>

    {data && data.total > data.page_size && <div className="flex items-center justify-between">
      <Button variant="outline" disabled={page <= 1 || loading} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button>
      <span className="text-sm text-muted-foreground">Page {page} of {totalPages} · {data.total} event(s)</span>
      <Button variant="outline" disabled={page >= totalPages || loading} onClick={() => setPage((value) => value + 1)}>Next</Button>
    </div>}
  </div>;
}
