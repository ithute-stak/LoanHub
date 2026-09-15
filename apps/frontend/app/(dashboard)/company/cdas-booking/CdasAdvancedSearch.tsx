"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Search, SlidersHorizontal } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { CdasAdvancedSearchParams, CdasAdvancedSearchResponse } from "@/types/cdasAdvancedSearch";

interface FilterState {
  q: string;
  employer: string;
  agency: string;
  decision: string;
  state: string;
  pipeline_stage: string;
  assigned_to_user_id: string;
  quality: "all" | "clean" | "issues";
  booking_from: string;
  booking_to: string;
  analyzed_from: string;
  analyzed_to: string;
  min_capacity: string;
  max_capacity: string;
  min_deduction: string;
  max_deduction: string;
}

const EMPTY_FILTERS: FilterState = {
  q: "",
  employer: "",
  agency: "",
  decision: "",
  state: "",
  pipeline_stage: "",
  assigned_to_user_id: "",
  quality: "all",
  booking_from: "",
  booking_to: "",
  analyzed_from: "",
  analyzed_to: "",
  min_capacity: "",
  max_capacity: "",
  min_deduction: "",
  max_deduction: "",
};

function money(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `M ${Number(value).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

function labelize(value?: string | null) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function numberOrUndefined(value: string) {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function buildParams(filters: FilterState): CdasAdvancedSearchParams {
  return {
    q: filters.q.trim() || undefined,
    employer: filters.employer || undefined,
    agency: filters.agency || undefined,
    decision: filters.decision || undefined,
    state: filters.state || undefined,
    pipeline_stage: filters.pipeline_stage || undefined,
    assigned_to_user_id: filters.assigned_to_user_id || undefined,
    quality: filters.quality,
    booking_from: filters.booking_from || undefined,
    booking_to: filters.booking_to || undefined,
    analyzed_from: filters.analyzed_from || undefined,
    analyzed_to: filters.analyzed_to || undefined,
    min_capacity: numberOrUndefined(filters.min_capacity),
    max_capacity: numberOrUndefined(filters.max_capacity),
    min_deduction: numberOrUndefined(filters.min_deduction),
    max_deduction: numberOrUndefined(filters.max_deduction),
    limit: 200,
  };
}

export function CdasAdvancedSearchView() {
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [data, setData] = useState<CdasAdvancedSearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const runSearch = useCallback(async (nextFilters: FilterState) => {
    setLoading(true);
    setError("");
    try {
      setData(await cdasBookingApi.advancedSearch(buildParams(nextFilters)));
    } catch (error: any) {
      setError(error?.response?.data?.detail || "Could not search CDAS records.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void runSearch(EMPTY_FILTERS); }, [runSearch]);

  function setField<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS);
    void runSearch(EMPTY_FILTERS);
  }

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><SlidersHorizontal className="h-5 w-5"/></div>
            <div>
              <CardTitle>CDAS Advanced Search & Filters</CardTitle>
              <CardDescription>Search the immutable analysis archive and live booking workflow together. Filters are read-only and do not change CDAS decisions or workflow state.</CardDescription>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => void runSearch(filters)} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="xl:col-span-2"><label className="mb-1 block text-xs font-medium text-muted-foreground">Search identity / employer / agency / reference</label><Input value={filters.q} onChange={(event) => setField("q", event.target.value)} placeholder="Name, employee no, NID, employer, agency, reference…"/></div>
          <FilterSelect label="Employer" value={filters.employer} onChange={(value) => setField("employer", value)} options={data?.options.employers || []}/>
          <FilterSelect label="Agency" value={filters.agency} onChange={(value) => setField("agency", value)} options={data?.options.agencies || []}/>
          <FilterSelect label="Decision" value={filters.decision} onChange={(value) => setField("decision", value)} options={data?.options.decisions || []}/>
          <FilterSelect label="Opportunity state" value={filters.state} onChange={(value) => setField("state", value)} options={data?.options.states || []}/>
          <FilterSelect label="Pipeline stage" value={filters.pipeline_stage} onChange={(value) => setField("pipeline_stage", value)} options={data?.options.pipeline_stages || []}/>
          <div><label className="mb-1 block text-xs font-medium text-muted-foreground">Assigned officer</label><select value={filters.assigned_to_user_id} onChange={(event) => setField("assigned_to_user_id", event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="">All officers</option><option value="unassigned">Unassigned</option>{data?.options.officers.map((officer) => <option key={officer.user_id} value={officer.user_id}>{officer.name}{officer.is_active ? "" : " (inactive)"}</option>)}</select></div>
          <div><label className="mb-1 block text-xs font-medium text-muted-foreground">Data quality</label><select value={filters.quality} onChange={(event) => setField("quality", event.target.value as FilterState["quality"])} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="all">All records</option><option value="clean">Clean only</option><option value="issues">Issues only</option></select></div>
          <DateInput label="Booking from" value={filters.booking_from} onChange={(value) => setField("booking_from", value)}/>
          <DateInput label="Booking to" value={filters.booking_to} onChange={(value) => setField("booking_to", value)}/>
          <DateInput label="Analyzed from" value={filters.analyzed_from} onChange={(value) => setField("analyzed_from", value)}/>
          <DateInput label="Analyzed to" value={filters.analyzed_to} onChange={(value) => setField("analyzed_to", value)}/>
          <NumberInput label="Min capacity" value={filters.min_capacity} onChange={(value) => setField("min_capacity", value)}/>
          <NumberInput label="Max capacity" value={filters.max_capacity} onChange={(value) => setField("max_capacity", value)}/>
          <NumberInput label="Min deduction" value={filters.min_deduction} onChange={(value) => setField("min_deduction", value)}/>
          <NumberInput label="Max deduction" value={filters.max_deduction} onChange={(value) => setField("max_deduction", value)}/>
        </div>
        <div className="flex flex-wrap gap-2"><Button onClick={() => void runSearch(filters)} disabled={loading}><Search className="mr-2 h-4 w-4"/>{loading ? "Searching…" : "Search"}</Button><Button variant="outline" onClick={clearFilters} disabled={loading}>Clear filters</Button></div>
      </CardContent>
    </Card>

    {data && <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Summary label="Archive matches" value={`${data.summary.analysis_matches} / ${data.summary.analysis_total}`}/>
        <Summary label="Opportunity matches" value={`${data.summary.opportunity_matches} / ${data.summary.opportunity_total}`}/>
        <Summary label="Archive displayed" value={`${data.analyses.length}${data.truncated.analyses ? "+" : ""}`}/>
        <Summary label="Opportunities displayed" value={`${data.opportunities.length}${data.truncated.opportunities ? "+" : ""}`}/>
      </div>

      <Card>
        <CardHeader><CardTitle>Analysis Archive</CardTitle><CardDescription>Historical structured CDAS analyses. Newest records remain first after filters are applied.</CardDescription></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm"><thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="p-2">Client</th><th className="p-2">Employer</th><th className="p-2">Agency</th><th className="p-2">Decision</th><th className="p-2">Capacity</th><th className="p-2">Next booking</th><th className="p-2">Quality</th><th className="p-2">Analyzed</th></tr></thead><tbody>{data.analyses.map((item) => <tr key={item.id} className="border-b align-top"><td className="p-2"><div className="font-medium">{item.client_name || "Unnamed client"}</div><div className="text-xs text-muted-foreground">{item.client_reference || item.employee_no || item.nid || "No strong reference"}</div></td><td className="p-2">{item.employer || "—"}</td><td className="p-2">{item.current_agency_name || "—"}</td><td className="p-2"><Badge variant="outline">{labelize(item.decision)}</Badge></td><td className="p-2">{money(item.assessed_available_amount)}</td><td className="p-2">{dateLabel(item.next_possible_booking_date)}</td><td className="p-2">{item.data_quality_issue_count ? <Badge variant="outline">{item.data_quality_issue_count} issue{item.data_quality_issue_count === 1 ? "" : "s"}</Badge> : <Badge variant="secondary">Clean</Badge>}</td><td className="p-2">{dateLabel(item.analyzed_at)}</td></tr>)}</tbody></table>
          {!data.analyses.length && <div className="py-10 text-center text-sm text-muted-foreground">No archived analyses match the selected filters.</div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Booking Opportunities</CardTitle><CardDescription>Current deduplicated booking workflow records matching the operational filters.</CardDescription></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[1050px] text-sm"><thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="p-2">Client</th><th className="p-2">Employer</th><th className="p-2">Agency</th><th className="p-2">State</th><th className="p-2">Pipeline</th><th className="p-2">Officer</th><th className="p-2">Deduction</th><th className="p-2">Capacity</th><th className="p-2">Booking date</th></tr></thead><tbody>{data.opportunities.map((item) => <tr key={item.id} className="border-b align-top"><td className="p-2"><div className="font-medium">{item.client_name || "CDAS client"}</div><div className="text-xs text-muted-foreground">{item.client_reference || item.opportunity_reference_no || "No reference"}</div></td><td className="p-2">{item.employer || "—"}</td><td className="p-2">{item.opportunity_agency_name || "—"}</td><td className="p-2"><Badge variant="outline">{labelize(item.state)}</Badge></td><td className="p-2">{labelize(item.pipeline_stage)}</td><td className="p-2">{item.assigned_to_name || "Unassigned"}</td><td className="p-2">{money(item.opportunity_deduction_amount)}</td><td className="p-2">{money(item.assessed_available_amount)}</td><td className="p-2">{dateLabel(item.booking_open_date)}</td></tr>)}</tbody></table>
          {!data.opportunities.length && <div className="py-10 text-center text-sm text-muted-foreground">No booking opportunities match the selected filters.</div>}
        </CardContent>
      </Card>
    </>}
  </div>;
}

function Summary({ label, value }: { label: string; value: string }) {
  return <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground">{label}</div><div className="mt-1 text-xl font-semibold">{value}</div></CardContent></Card>;
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <div><label className="mb-1 block text-xs font-medium text-muted-foreground">{label}</label><select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm"><option value="">All</option>{options.map((option) => <option key={option} value={option}>{labelize(option)}</option>)}</select></div>;
}

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <div><label className="mb-1 block text-xs font-medium text-muted-foreground">{label}</label><Input type="date" value={value} onChange={(event) => onChange(event.target.value)}/></div>;
}

function NumberInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <div><label className="mb-1 block text-xs font-medium text-muted-foreground">{label}</label><Input type="number" step="0.01" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Any"/></div>;
}
