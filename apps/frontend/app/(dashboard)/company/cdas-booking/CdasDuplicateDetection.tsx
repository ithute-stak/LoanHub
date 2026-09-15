"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CopyCheck, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CdasDuplicateCandidate, CdasDuplicateDetection, CdasDuplicateProfileSummary } from "@/types/cdasDuplicateDetection";

function ProfilePanel({ title, value }: { title: string; value: CdasDuplicateProfileSummary }) {
  const rows = [
    ["Name", value.client_name],
    ["Client reference", value.client_reference],
    ["Employee no.", value.employee_no],
    ["NID", value.nid],
    ["Employer", value.employer],
    ["Current agency", value.current_agency_name],
  ];
  return <div className="rounded-lg border p-3">
    <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
    <div className="space-y-2">{rows.map(([label, item]) => <div key={label} className="grid grid-cols-[120px_1fr] gap-2 text-sm"><div className="text-muted-foreground">{label}</div><div className="break-words font-medium">{item || "—"}</div></div>)}</div>
    <div className="mt-3 text-xs text-muted-foreground">{value.analysis_count} analysis record(s) • {value.opportunity_count} opportunity record(s)</div>
  </div>;
}

function CandidateCard({ item }: { item: CdasDuplicateCandidate }) {
  return <Card>
    <CardHeader>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div><CardTitle className="text-base">Possible duplicate client profiles</CardTitle><CardDescription>{item.evidence.join(" • ")}</CardDescription></div>
        <Badge variant={item.confidence === "HIGH" ? "default" : "secondary"}>{item.confidence} confidence</Badge>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-2"><ProfilePanel title="Profile A" value={item.left}/><ProfilePanel title="Profile B" value={item.right}/></div>
      {item.shared_identifiers.length ? <div className="rounded-lg border bg-muted/20 p-3"><div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Exact shared identifiers</div><div className="mt-2 flex flex-wrap gap-2">{item.shared_identifiers.map((shared, index) => <Badge key={`${shared.value}-${index}`} variant="outline">{shared.left_field} ↔ {shared.right_field}: {shared.value}</Badge>)}</div></div> : null}
      <div className="text-xs text-muted-foreground">Reason codes: {item.reason_codes.join(", ")}. Review only — LoanHub does not merge these profiles automatically.</div>
    </CardContent>
  </Card>;
}

export function CdasDuplicateDetectionView() {
  const [data, setData] = useState<CdasDuplicateDetection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [confidence, setConfidence] = useState<"all" | "HIGH" | "MEDIUM">("all");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setData(await cdasBookingApi.getDuplicateDetection()); }
    catch { setError("Could not load CDAS duplicate detection."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const visible = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    return data.items.filter((item) => {
      if (confidence !== "all" && item.confidence !== confidence) return false;
      if (!needle) return true;
      return [item.left.client_name, item.left.client_reference, item.left.employee_no, item.left.nid, item.left.employer, item.right.client_name, item.right.client_reference, item.right.employee_no, item.right.nid, item.right.employer]
        .some((value) => String(value || "").toLowerCase().includes(needle));
    });
  }, [data, query, confidence]);

  if (!data && loading) return <Card><CardContent className="py-16 text-center text-sm text-muted-foreground">Loading duplicate detection…</CardContent></Card>;
  if (!data) return <Card><CardContent className="py-10 text-center text-sm text-destructive">{error || "Duplicate detection could not be loaded."}</CardContent></Card>;

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-lg border bg-muted/40 p-2"><CopyCheck className="h-5 w-5"/></div><div><CardTitle>CDAS Client Duplicate Detection</CardTitle><CardDescription>Review-only duplicate candidates based on exact identity evidence. No fuzzy name matching and no automatic profile merging.</CardDescription></div></div>
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Profiles checked</div><div className="mt-1 text-xl font-semibold">{data.summary.profiles_checked}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Candidate pairs</div><div className="mt-1 text-xl font-semibold">{data.summary.candidate_pairs}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">High confidence</div><div className="mt-1 text-xl font-semibold">{data.summary.high_confidence_pairs}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Medium confidence</div><div className="mt-1 text-xl font-semibold">{data.summary.medium_confidence_pairs}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Affected profiles</div><div className="mt-1 text-xl font-semibold">{data.summary.affected_client_profiles}</div></div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input aria-label="Search duplicate candidates" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, reference, employee no., NID or employer" className="h-10 flex-1 rounded-md border bg-background px-3 text-sm"/>
          <div className="flex gap-2"><Button size="sm" variant={confidence === "all" ? "default" : "outline"} onClick={() => setConfidence("all")}>All</Button><Button size="sm" variant={confidence === "HIGH" ? "default" : "outline"} onClick={() => setConfidence("HIGH")}>High</Button><Button size="sm" variant={confidence === "MEDIUM" ? "default" : "outline"} onClick={() => setConfidence("MEDIUM")}>Medium</Button></div>
        </div>
        <div className="text-xs text-muted-foreground">{data.policy.description}</div>
      </CardContent>
    </Card>

    {!visible.length ? <Card><CardContent className="py-14 text-center text-sm text-muted-foreground">No duplicate candidates match this view.</CardContent></Card> : <div className="space-y-4">{visible.map((item) => <CandidateCard key={item.candidate_id} item={item}/>)}</div>}
  </div>;
}
