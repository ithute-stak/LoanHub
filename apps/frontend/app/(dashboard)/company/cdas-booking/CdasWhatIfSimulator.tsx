"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Calculator, CalendarClock, CheckCircle2, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { CdasBookingOpportunity } from "@/types/cdasBooking";
import type { CdasWhatIfResult } from "@/types/cdasWhatIf";

type Mode = "installment" | "loan";

function money(value?: number | null) {
  if (value === null || value === undefined) return "Not available";
  return `M ${Number(value).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value?: string | null) {
  if (!value) return "No date";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString("en-ZA", { day: "2-digit", month: "short", year: "numeric" });
}

function statusLabel(value: CdasWhatIfResult["status"]) {
  if (value === "FITS_NOW") return "Fits current capacity";
  if (value === "FITS_AFTER_RELEASE") return "Fits after future release";
  if (value === "EXCEEDS_KNOWN_CAPACITY") return "Exceeds known capacity";
  return "Capacity unknown";
}

export function CdasWhatIfSimulator() {
  const [opportunities, setOpportunities] = useState<CdasBookingOpportunity[]>([]);
  const [opportunityId, setOpportunityId] = useState("");
  const [mode, setMode] = useState<Mode>("installment");
  const [installment, setInstallment] = useState("");
  const [amount, setAmount] = useState("");
  const [term, setTerm] = useState("12");
  const [rate, setRate] = useState("");
  const [result, setResult] = useState<CdasWhatIfResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [error, setError] = useState("");

  async function loadOpportunities() {
    setLoading(true);
    setError("");
    try {
      const response = await cdasBookingApi.listOpportunities();
      const open = response.items.filter((item) => item.state !== "BOOKED");
      setOpportunities(open);
      setOpportunityId((current) => current || open[0]?.id || "");
    } catch {
      setError("Could not load saved CDAS booking opportunities.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadOpportunities(); }, []);

  const selected = useMemo(
    () => opportunities.find((item) => item.id === opportunityId) || null,
    [opportunities, opportunityId],
  );

  async function simulate() {
    if (!opportunityId) {
      setError("Select a saved CDAS opportunity first.");
      return;
    }

    const payload = { opportunity_id: opportunityId } as {
      opportunity_id: string;
      proposed_installment?: number;
      proposed_amount?: number;
      term_months?: number;
      annual_interest_rate?: number;
    };

    if (mode === "installment") {
      const value = Number(installment);
      if (!Number.isFinite(value) || value <= 0) {
        setError("Enter a proposed monthly installment greater than zero.");
        return;
      }
      payload.proposed_installment = value;
    } else {
      const principal = Number(amount);
      const months = Number(term);
      const annualRate = Number(rate);
      if (!Number.isFinite(principal) || principal <= 0 || !Number.isInteger(months) || months <= 0 || !Number.isFinite(annualRate) || annualRate < 0) {
        setError("Enter a valid proposed amount, term and annual interest rate.");
        return;
      }
      payload.proposed_amount = principal;
      payload.term_months = months;
      payload.annual_interest_rate = annualRate;
    }

    setSimulating(true);
    setError("");
    try {
      setResult(await cdasBookingApi.simulateWhatIf(payload));
    } catch {
      setResult(null);
      setError("The what-if simulation could not be completed. Check the saved CDAS data and scenario values.");
    } finally {
      setSimulating(false);
    }
  }

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><Calculator className="h-5 w-5"/></div>
            <div>
              <CardTitle>CDAS What-If Simulator</CardTitle>
              <CardDescription>Test a proposed monthly deduction against a saved CDAS opportunity without changing the real analysis or booking record.</CardDescription>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => void loadOpportunities()} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh opportunities
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}

        {!loading && !opportunities.length ? <div className="rounded-lg border p-6 text-center text-sm text-muted-foreground">Save a CDAS booking opportunity first, then return here to simulate scenarios.</div> : <>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="cdas-opportunity">Saved CDAS opportunity</label>
              <select id="cdas-opportunity" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={opportunityId} onChange={(event) => { setOpportunityId(event.target.value); setResult(null); }}>
                {opportunities.map((item) => <option key={item.id} value={item.id}>{item.client_name || item.client_reference || "CDAS client"} — {item.opportunity_agency_name || "Agency not captured"}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <div className="text-sm font-medium">Scenario mode</div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant={mode === "installment" ? "default" : "outline"} onClick={() => { setMode("installment"); setResult(null); }}>Installment only</Button>
                <Button type="button" variant={mode === "loan" ? "default" : "outline"} onClick={() => { setMode("loan"); setResult(null); }}>Loan scenario</Button>
              </div>
            </div>
          </div>

          {selected && <div className="grid gap-3 rounded-lg border bg-muted/20 p-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
            <div><div className="text-xs text-muted-foreground">Client</div><div className="font-medium">{selected.client_name || selected.client_reference || "CDAS client"}</div></div>
            <div><div className="text-xs text-muted-foreground">Booking date</div><div className="font-medium">{dateLabel(selected.booking_open_date)}</div></div>
            <div><div className="text-xs text-muted-foreground">Current opportunity</div><div className="font-medium">{money(selected.opportunity_deduction_amount)}</div></div>
            <div><div className="text-xs text-muted-foreground">Agency</div><div className="font-medium">{selected.opportunity_agency_name || "Not captured"}</div></div>
          </div>}

          {mode === "installment" ? <div className="max-w-md space-y-2">
            <label className="text-sm font-medium" htmlFor="proposed-installment">Proposed monthly installment</label>
            <Input id="proposed-installment" type="number" min="0.01" step="0.01" value={installment} onChange={(event) => setInstallment(event.target.value)} placeholder="e.g. 1500.00"/>
          </div> : <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="proposed-amount">Proposed loan amount</label><Input id="proposed-amount" type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="e.g. 25000"/></div>
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="term-months">Term (months)</label><Input id="term-months" type="number" min="1" max="240" step="1" value={term} onChange={(event) => setTerm(event.target.value)}/></div>
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="annual-rate">Annual interest rate (%)</label><Input id="annual-rate" type="number" min="0" max="500" step="0.01" value={rate} onChange={(event) => setRate(event.target.value)} placeholder="e.g. 24"/></div>
          </div>}

          <Button type="button" onClick={() => void simulate()} disabled={simulating || loading}>
            <Calculator className="mr-2 h-4 w-4"/>{simulating ? "Simulating..." : "Run what-if simulation"}
          </Button>
        </>}
      </CardContent>
    </Card>

    {result && <>
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div><CardTitle>{result.client_name || result.client_reference || "CDAS client"}</CardTitle><CardDescription>Simulation as of {dateLabel(result.as_of)}. This result does not modify the saved opportunity.</CardDescription></div>
            <div className="flex flex-wrap gap-2"><Badge variant={result.fits_now ? "default" : "secondary"}>{statusLabel(result.status)}</Badge><Badge variant="outline">Confidence: {result.confidence.replaceAll("_", " ")}</Badge></div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Proposed installment</div><div className="mt-1 text-lg font-semibold">{money(result.scenario.proposed_installment)}</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Current CDAS capacity</div><div className="mt-1 text-lg font-semibold">{money(result.current_capacity)}</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Remaining capacity</div><div className="mt-1 text-lg font-semibold">{money(result.remaining_capacity)}</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Current shortfall</div><div className="mt-1 text-lg font-semibold">{money(result.shortfall)}</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Earliest estimated fit</div><div className="mt-1 text-lg font-semibold">{dateLabel(result.earliest_fit_date)}</div></div>
          </div>

          {result.fits_now ? <div className="flex gap-3 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4 text-sm"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0"/><div><div className="font-medium">The proposed installment fits the saved current CDAS capacity.</div><div className="mt-1 text-muted-foreground">Re-analyse fresh CDAS data before an actual booking because this simulator does not replace the live CDAS check.</div></div></div> : result.requires_waiting_for_release ? <div className="flex gap-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-sm"><CalendarClock className="mt-0.5 h-5 w-5 shrink-0"/><div><div className="font-medium">The installment does not fit now, but a saved future deduction window could create enough capacity by {dateLabel(result.earliest_fit_date)}.</div><div className="mt-1 text-muted-foreground">Estimated capacity at that point: {money(result.earliest_fit_capacity)}.</div></div></div> : <div className="flex gap-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-sm"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0"/><div><div className="font-medium">The proposed installment cannot be confirmed from the known saved capacity.</div><div className="mt-1 text-muted-foreground">Use a smaller scenario or re-analyse the client when CDAS data changes.</div></div></div>}

          {!!result.warnings.length && <div className="space-y-2"><div className="text-sm font-medium">Warnings</div>{result.warnings.map((warning) => <div key={warning} className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-sm">{warning}</div>)}</div>}
          <div className="rounded-md bg-muted/30 p-3 text-xs text-muted-foreground">{result.projection_note}</div>
        </CardContent>
      </Card>

      {!!result.release_windows.length && <Card>
        <CardHeader><CardTitle className="text-base">Saved future deduction windows</CardTitle><CardDescription>Indicative capacity releases found in the archived CDAS analysis.</CardDescription></CardHeader>
        <CardContent className="space-y-3">{result.release_windows.map((window) => <div key={window.booking_date} className="rounded-lg border p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div className="font-medium">{dateLabel(window.booking_date)}</div><div className="text-sm">Release {money(window.released_monthly_deduction)} • cumulative {money(window.cumulative_release)}</div></div>
          <div className="mt-3 space-y-2 text-sm">{window.deductions.map((row, index) => <div key={`${row.reference_no || row.item_code || "row"}-${index}`} className="flex flex-col justify-between gap-1 rounded-md bg-muted/30 p-2 sm:flex-row"><span>{row.agency_name || "Agency"}{row.reference_no ? ` • ${row.reference_no}` : ""}</span><span className="font-medium">{money(row.deduction_amount)}</span></div>)}</div>
        </div>)}</CardContent>
      </Card>}
    </>}
  </div>;
}
