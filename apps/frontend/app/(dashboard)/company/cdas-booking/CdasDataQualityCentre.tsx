"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, ShieldAlert } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasDataQualityCentre, CdasDataQualityIssue } from "@/types/cdasDataQuality";

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

function severityVariant(severity: string): "default" | "secondary" | "outline" {
  if (severity === "BLOCKER") return "default";
  if (severity === "WARNING") return "secondary";
  return "outline";
}

function IssueRow({ issue }: { issue: CdasDataQualityIssue }) {
  return <div className="rounded-lg border p-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="font-medium">{issue.label}</div>
      <Badge variant={severityVariant(issue.severity)}>{issue.severity}</Badge>
    </div>
    <p className="mt-1 text-sm text-muted-foreground">{issue.message}</p>
    {issue.deduction && <div className="mt-3 grid gap-2 rounded-md bg-muted/30 p-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
      <div><span className="text-muted-foreground">Agency</span><div className="font-medium">{issue.deduction.agency_name || "—"}</div></div>
      <div><span className="text-muted-foreground">Item / reference</span><div className="font-medium">{issue.deduction.item_code || "—"}{issue.deduction.reference_no ? ` • ${issue.deduction.reference_no}` : ""}</div></div>
      <div><span className="text-muted-foreground">Monthly deduction</span><div className="font-medium">{money(issue.deduction.deduction_amount)}</div></div>
      <div><span className="text-muted-foreground">Effective / expiry</span><div className="font-medium">{issue.deduction.effective_date || "—"} → {issue.deduction.expiry_date || "Missing"}</div></div>
    </div>}
  </div>;
}

export function CdasDataQualityCentreView() {
  const [data, setData] = useState<CdasDataQualityCentre | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"issues" | "blockers" | "all">("issues");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.getDataQuality());
    } catch {
      setError("Could not load the CDAS Data Quality Centre.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const items = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    return data.items.filter((item) => {
      if (view === "issues" && item.issue_count === 0) return false;
      if (view === "blockers" && item.blocker_count === 0) return false;
      if (!needle) return true;
      return [item.client_name, item.client_reference, item.employee_no, item.nid, item.employer, item.current_agency_name]
        .some((value) => String(value || "").toLowerCase().includes(needle));
    });
  }, [data, query, view]);

  if (!data && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading CDAS data quality…</CardContent></Card>;
  if (!data) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "CDAS data quality could not be loaded."}</CardContent></Card>;

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><ShieldAlert className="h-5 w-5"/></div>
            <div><CardTitle>CDAS Data Quality Centre</CardTitle><CardDescription>Review quality problems in each client&apos;s latest archived CDAS analysis. This workspace is diagnostic only: it never edits source CDAS data or changes a booking decision.</CardDescription></div>
          </div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Clients checked</div><div className="mt-1 text-xl font-semibold">{data.summary.clients_checked}</div><div className="text-xs text-muted-foreground">{data.summary.clients_with_issues} with issues</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Blocker clients</div><div className="mt-1 text-xl font-semibold">{data.summary.blocker_clients}</div><div className="text-xs text-muted-foreground">{data.summary.blocker_issues} blocker issues</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Warnings</div><div className="mt-1 text-xl font-semibold">{data.summary.warning_issues}</div><div className="text-xs text-muted-foreground">{data.summary.total_issues} total issues</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Affected monthly value</div><div className="mt-1 text-xl font-semibold">{money(data.summary.excluded_monthly_amount)}</div><div className="text-xs text-muted-foreground">blocked deduction rows</div></div>
        </div>
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
          <input aria-label="Search data quality" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search client, reference, employer or agency" className="h-10 flex-1 rounded-md border bg-background px-3 text-sm"/>
          <div className="flex flex-wrap gap-2"><Button size="sm" variant={view === "issues" ? "default" : "outline"} onClick={() => setView("issues")}>Needs attention</Button><Button size="sm" variant={view === "blockers" ? "default" : "outline"} onClick={() => setView("blockers")}>Blockers only</Button><Button size="sm" variant={view === "all" ? "default" : "outline"} onClick={() => setView("all")}>All clients</Button></div>
        </div>
        {!!data.categories.length && <div className="flex flex-wrap gap-2">{data.categories.map((category) => <Badge key={category.category} variant={severityVariant(category.severity)}>{category.label}: {category.count}</Badge>)}</div>}
      </CardContent>
    </Card>

    {!data.total ? <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">No archived CDAS client analyses are available yet.</CardContent></Card> : !items.length ? <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">No clients match the current data-quality filter.</CardContent></Card> : <div className="space-y-4">{items.map((item) => <Card key={item.client_key}>
      <CardHeader>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div><CardTitle className="text-lg">{item.client_name || item.client_reference || "CDAS client"}</CardTitle><CardDescription>{item.client_reference || item.employee_no || item.nid || "No strong identifier"}{item.employer ? ` • ${item.employer}` : ""}{item.current_agency_name ? ` • ${item.current_agency_name}` : ""}</CardDescription></div>
          <div className="flex flex-wrap gap-2"><Badge variant={item.blocker_count ? "default" : item.warning_count ? "secondary" : "outline"}>Quality {item.quality_score}/100</Badge>{item.blocker_count > 0 && <Badge variant="default">{item.blocker_count} blocker{item.blocker_count === 1 ? "" : "s"}</Badge>}{item.warning_count > 0 && <Badge variant="secondary">{item.warning_count} warning{item.warning_count === 1 ? "" : "s"}</Badge>}</div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3"><div>Latest analysis: {dateTime(item.latest_analyzed_at)}</div><div>Decision: {String(item.decision || "—").replaceAll("_", " ")}</div><div>Blocked monthly value: {money(item.excluded_monthly_amount)}</div></div>
        {!item.issues.length ? <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">No tracked quality issues in the latest analysis.</div> : <div className="space-y-2">{item.issues.map((issue, index) => <IssueRow key={`${issue.category}-${index}`} issue={issue}/>)}</div>}
      </CardContent>
    </Card>)}</div>}
  </div>;
}
