"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, RefreshCw, UserRound, Users } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { CdasClientProfileDetail, CdasClientProfileSummary } from "@/types/cdasBooking";

function money(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `M ${Number(value).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "—";
  const d = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

function dateTimeLabel(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("en-ZA", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function DecisionBadge({ decision }: { decision?: string | null }) {
  if (!decision) return <Badge variant="outline">No analysis</Badge>;
  const review = decision === "REVIEW_REQUIRED";
  return <Badge variant={review ? "outline" : decision === "BOOK_NOW" ? "default" : "secondary"} className={review ? "border-amber-500 text-amber-700 dark:text-amber-300" : ""}>{decision.replaceAll("_", " ")}</Badge>;
}

export function CdasClientProfiles() {
  const [profiles, setProfiles] = useState<CdasClientProfileSummary[]>([]);
  const [selected, setSelected] = useState<CdasClientProfileDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await cdasBookingApi.listClientProfiles();
      setProfiles(data.items);
      if (selected) {
        const refreshed = await cdasBookingApi.getClientProfile(selected.client_key);
        setSelected(refreshed);
      }
    } catch {
      setError("Could not load CDAS client profiles.");
    } finally {
      setLoading(false);
    }
  }, [selected?.client_key]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function openProfile(item: CdasClientProfileSummary) {
    setDetailLoading(true);
    setError("");
    try {
      setSelected(await cdasBookingApi.getClientProfile(item.client_key));
    } catch {
      setError("Could not open this CDAS client profile.");
    } finally {
      setDetailLoading(false);
    }
  }

  if (selected) {
    return <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" onClick={() => setSelected(null)}><ArrowLeft className="mr-2 h-4 w-4"/>All client profiles</Button>
        <Button variant="outline" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh profile</Button>
      </div>

      {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex items-start gap-3">
              <div className="rounded-lg border bg-muted/40 p-2"><UserRound className="h-5 w-5"/></div>
              <div>
                <CardTitle>{selected.client_name || selected.profile.full_name || "CDAS client"}</CardTitle>
                <CardDescription>{selected.employer || selected.profile.employer || "Employer not captured"}</CardDescription>
              </div>
            </div>
            <DecisionBadge decision={selected.decision}/>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Client reference</div><div className="font-medium">{selected.client_reference || "—"}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Employee number</div><div className="font-medium">{selected.employee_no || selected.profile.employee_no || "—"}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">NID</div><div className="font-medium">{selected.nid || selected.profile.nid || "—"}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Current CDAS agency</div><div className="font-medium">{selected.current_agency_name || "—"}</div>{selected.current_agency_code && <div className="text-xs text-muted-foreground">Agency {selected.current_agency_code}</div>}</div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Available capacity</div><div className="font-semibold">{money(selected.assessed_available_amount)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Amount owing / term</div><div className="font-semibold">{money(selected.amount_owing)}</div><div className="text-xs text-muted-foreground">{selected.booking_months ? `${selected.booking_months} month(s)` : "Term not calculated"}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Next possible booking</div><div className="font-semibold">{dateLabel(selected.next_possible_booking_date)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Profile history</div><div className="font-semibold">{selected.analysis_count} analyses</div><div className="text-xs text-muted-foreground">{selected.opportunity_count} booking opportunities</div></div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Current deductions</CardTitle><CardDescription>The most recent archived CDAS position for this client.</CardDescription></CardHeader>
        <CardContent>{!selected.current_deductions.length ? <div className="py-8 text-center text-sm text-muted-foreground">No deduction rows are available in the latest analysis.</div> : <div className="overflow-x-auto rounded-lg border"><Table><TableHeader><TableRow><TableHead>Agency</TableHead><TableHead>Reference</TableHead><TableHead>Deduction</TableHead><TableHead>Effective</TableHead><TableHead>Expiry</TableHead><TableHead>Status</TableHead><TableHead>Quality</TableHead></TableRow></TableHeader><TableBody>{selected.current_deductions.map((row) => <TableRow key={`${row.item_code}-${row.reference_no}`}><TableCell><div>{row.agency_name}</div><div className="text-xs text-muted-foreground">Item {row.item_code}</div></TableCell><TableCell>{row.reference_no || "—"}</TableCell><TableCell>{money(row.deduction_amount)}</TableCell><TableCell>{dateLabel(row.effective_date)}</TableCell><TableCell>{dateLabel(row.expiry_date)}</TableCell><TableCell><Badge variant="secondary">{row.booking_status.replaceAll("_", " ")}</Badge></TableCell><TableCell>{row.data_quality_status === "OK" ? <Badge variant="secondary">Valid</Badge> : <Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-300">{row.data_quality_status.replaceAll("_", " ")}</Badge>}</TableCell></TableRow>)}</TableBody></Table></div>}</CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Analysis history</CardTitle><CardDescription>Every distinct archived analysis version for this client.</CardDescription></CardHeader>
        <CardContent>{!selected.analyses.length ? <div className="py-8 text-center text-sm text-muted-foreground">No archived analyses.</div> : <div className="overflow-x-auto rounded-lg border"><Table><TableHeader><TableRow><TableHead>Analyzed</TableHead><TableHead>Decision</TableHead><TableHead>Capacity</TableHead><TableHead>Amount owing / term</TableHead><TableHead>Next booking</TableHead><TableHead>Quality</TableHead></TableRow></TableHeader><TableBody>{selected.analyses.map((analysis) => <TableRow key={analysis.id}><TableCell><div>{dateTimeLabel(analysis.analyzed_at)}</div><div className="text-xs text-muted-foreground">{analysis.analyzed_by_name || "Company user"}</div></TableCell><TableCell><DecisionBadge decision={analysis.decision}/></TableCell><TableCell>{money(analysis.assessed_available_amount)}</TableCell><TableCell><div>{money(analysis.amount_owing)}</div><div className="text-xs text-muted-foreground">{analysis.booking_months ? `${analysis.booking_months} month(s)` : "Term not calculated"}</div></TableCell><TableCell>{dateLabel(analysis.next_possible_booking_date)}</TableCell><TableCell>{analysis.data_quality_issue_count ? <Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-300">{analysis.data_quality_issue_count} issue{analysis.data_quality_issue_count === 1 ? "" : "s"}</Badge> : <Badge variant="secondary">Valid</Badge>}</TableCell></TableRow>)}</TableBody></Table></div>}</CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Booking history</CardTitle><CardDescription>All saved CDAS booking opportunities associated with this client.</CardDescription></CardHeader>
        <CardContent>{!selected.opportunities.length ? <div className="py-8 text-center text-sm text-muted-foreground">No booking opportunities have been saved for this client.</div> : <div className="overflow-x-auto rounded-lg border"><Table><TableHeader><TableRow><TableHead>Agency</TableHead><TableHead>Reference</TableHead><TableHead>Deduction</TableHead><TableHead>Booking opens</TableHead><TableHead>Expiry</TableHead><TableHead>State</TableHead></TableRow></TableHeader><TableBody>{selected.opportunities.map((item) => <TableRow key={item.id}><TableCell>{item.opportunity_agency_name || "—"}</TableCell><TableCell>{item.opportunity_reference_no || "—"}</TableCell><TableCell>{money(item.opportunity_deduction_amount)}</TableCell><TableCell>{dateLabel(item.booking_open_date)}</TableCell><TableCell>{dateLabel(item.opportunity_expiry_date)}</TableCell><TableCell><Badge variant={item.state === "BOOK_NOW" ? "default" : "secondary"}>{item.state.replaceAll("_", " ")}</Badge></TableCell></TableRow>)}</TableBody></Table></div>}</CardContent>
      </Card>
    </div>;
  }

  return <Card>
    <CardHeader>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="rounded-lg border bg-muted/40 p-2"><Users className="h-5 w-5"/></div>
          <div><CardTitle>CDAS Client Profiles</CardTitle><CardDescription>One permanent client-level view combining identity, employer, latest deductions, analysis versions and booking history.</CardDescription></div>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
      </div>
    </CardHeader>
    <CardContent>
      {error && <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
      {loading && !profiles.length ? <div className="py-12 text-center text-sm text-muted-foreground">Loading client profiles…</div> : !profiles.length ? <div className="py-12 text-center text-sm text-muted-foreground">No CDAS client profiles exist yet. Analyze a client to create the first profile.</div> : <div className="overflow-x-auto rounded-lg border"><Table><TableHeader><TableRow><TableHead>Client</TableHead><TableHead>Employer</TableHead><TableHead>Latest analysis</TableHead><TableHead>Decision</TableHead><TableHead>Capacity</TableHead><TableHead>Next booking</TableHead><TableHead>History</TableHead><TableHead className="text-right">Profile</TableHead></TableRow></TableHeader><TableBody>{profiles.map((item) => <TableRow key={item.client_key}><TableCell><div className="font-medium">{item.client_name || "CDAS client"}</div><div className="text-xs text-muted-foreground">{item.client_reference || item.employee_no || item.nid || "No reference"}</div></TableCell><TableCell>{item.employer || "—"}</TableCell><TableCell className="whitespace-nowrap">{dateTimeLabel(item.latest_analyzed_at)}</TableCell><TableCell><DecisionBadge decision={item.decision}/></TableCell><TableCell className="whitespace-nowrap">{money(item.assessed_available_amount)}</TableCell><TableCell className="whitespace-nowrap">{dateLabel(item.next_possible_booking_date)}</TableCell><TableCell><div>{item.analysis_count} analyses</div><div className="text-xs text-muted-foreground">{item.opportunity_count} opportunities · {item.booked_count} booked</div></TableCell><TableCell className="text-right"><Button size="sm" variant="outline" disabled={detailLoading} onClick={() => void openProfile(item)}>Open profile</Button></TableCell></TableRow>)}</TableBody></Table></div>}
    </CardContent>
  </Card>;
}
