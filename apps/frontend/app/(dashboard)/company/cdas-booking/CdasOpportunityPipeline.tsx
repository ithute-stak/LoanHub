"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { KanbanSquare, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasPipelineStage } from "@/types/cdasBooking";
import type { CdasOpportunityPipeline } from "@/types/cdasOpportunityPipeline";

const STAGE_OPTIONS: Array<{ id: CdasPipelineStage; label: string }> = [
  { id: "identified", label: "Identified" },
  { id: "contact_client", label: "Contact Client" },
  { id: "documents_required", label: "Documents Required" },
  { id: "ready_to_book", label: "Ready to Book" },
  { id: "booking_submitted", label: "Booking Submitted" },
  { id: "approved", label: "Approved" },
  { id: "failed", label: "Failed" },
  { id: "booked", label: "Booked" },
];

function money(value?: number | null) {
  return `M ${Number(value || 0).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "No booking date";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

export function CdasOpportunityPipelineView() {
  const [data, setData] = useState<CdasOpportunityPipeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.getOpportunityPipeline());
    } catch {
      setError("Could not load the CDAS opportunity pipeline.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function moveOpportunity(id: string, stage: CdasPipelineStage) {
    setUpdatingId(id);
    setError("");
    try {
      await cdasBookingApi.updatePipelineStage(id, stage);
      await refresh();
    } catch (error: any) {
      setError(error?.response?.data?.detail || "Could not update the opportunity pipeline stage.");
    } finally {
      setUpdatingId(null);
    }
  }

  const stages = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    if (!needle) return data.stages;
    return data.stages.map((stage) => ({
      ...stage,
      items: stage.items.filter((item) =>
        [
          item.client_name,
          item.client_reference,
          item.opportunity_agency_name,
          item.opportunity_reference_no,
        ].some((value) => String(value || "").toLowerCase().includes(needle)),
      ),
    }));
  }, [data, query]);

  if (!data && loading) {
    return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading opportunity pipeline…</CardContent></Card>;
  }

  if (!data) {
    return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "Opportunity pipeline could not be loaded."}</CardContent></Card>;
  }

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><KanbanSquare className="h-5 w-5"/></div>
            <div>
              <CardTitle>CDAS Opportunity Pipeline</CardTitle>
              <CardDescription>Move each saved CDAS opportunity from identification through client contact, documents, submission, approval and final booking. Failed work is removed from active reminders and can be reopened later.</CardDescription>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Active opportunities</div><div className="mt-1 text-xl font-semibold">{data.summary.active}</div><div className="text-xs text-muted-foreground">{money(data.summary.active_monthly_deduction_value)} monthly value</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Failed</div><div className="mt-1 text-xl font-semibold">{data.summary.failed}</div><div className="text-xs text-muted-foreground">{money(data.summary.failed_monthly_deduction_value)} monthly value</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Booked</div><div className="mt-1 text-xl font-semibold">{data.summary.booked}</div><div className="text-xs text-muted-foreground">{money(data.summary.booked_monthly_deduction_value)} monthly value</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Total pipeline records</div><div className="mt-1 text-xl font-semibold">{data.total}</div></div>
        </div>
        <input aria-label="Search pipeline" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search client, reference or agency" className="h-10 w-full rounded-md border bg-background px-3 text-sm sm:max-w-md"/>
      </CardContent>
    </Card>

    <div className="overflow-x-auto pb-3">
      <div className="flex min-w-max gap-4">
        {stages.map((stage) => <section key={stage.id} className="w-[300px] shrink-0 rounded-xl border bg-muted/10 p-3">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div><div className="font-semibold">{stage.label}</div><div className="text-xs text-muted-foreground">{money(stage.monthly_deduction_value)}</div></div>
            <Badge variant={stage.id === "failed" ? "outline" : stage.id === "booked" ? "secondary" : "default"}>{stage.items.length}{query ? ` / ${stage.count}` : ""}</Badge>
          </div>
          <div className="space-y-3">
            {!stage.items.length && <div className="rounded-lg border border-dashed p-5 text-center text-xs text-muted-foreground">No opportunities in this stage.</div>}
            {stage.items.map((item) => <Card key={item.id} className={stage.id === "failed" ? "border-amber-500/40" : ""}>
              <CardHeader className="p-4 pb-2">
                <CardTitle className="text-base">{item.client_name || item.client_reference || "CDAS client"}</CardTitle>
                <CardDescription>{item.opportunity_agency_name || "Agency not captured"}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 p-4 pt-2 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div><div className="text-xs text-muted-foreground">Deduction</div><div className="font-medium">{money(item.opportunity_deduction_amount)}</div></div>
                  <div><div className="text-xs text-muted-foreground">Booking date</div><div className="font-medium">{dateLabel(item.booking_open_date)}</div></div>
                </div>
                {item.opportunity_reference_no && <div className="truncate text-xs text-muted-foreground">Ref: {item.opportunity_reference_no}</div>}
                <div className="space-y-1">
                  <label className="text-xs font-medium" htmlFor={`pipeline-${item.id}`}>Pipeline stage</label>
                  <select
                    id={`pipeline-${item.id}`}
                    value={item.pipeline_stage}
                    disabled={updatingId === item.id || item.pipeline_stage === "booked"}
                    onChange={(event) => void moveOpportunity(item.id, event.target.value as CdasPipelineStage)}
                    className="h-9 w-full rounded-md border bg-background px-2 text-xs"
                  >
                    {STAGE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                  </select>
                  {item.pipeline_stage === "booked" && <div className="text-xs text-muted-foreground">Booked is terminal.</div>}
                </div>
              </CardContent>
            </Card>)}
          </div>
        </section>)}
      </div>
    </div>
  </div>;
}
