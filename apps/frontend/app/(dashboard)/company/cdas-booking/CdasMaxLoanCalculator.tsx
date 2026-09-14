"use client";

import { useEffect, useMemo, useState } from "react";
import { Calculator, RefreshCw } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { CdasBookingOpportunity } from "@/types/cdasBooking";
import type { CdasMaxLoanResult } from "@/types/cdasMaxLoan";

function money(value?: number | null) {
  if (value === null || value === undefined) return "Not available";
  return `M ${Number(value).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function CdasMaxLoanCalculator() {
  const [opportunities, setOpportunities] = useState<CdasBookingOpportunity[]>([]);
  const [opportunityId, setOpportunityId] = useState("");
  const [term, setTerm] = useState("12");
  const [rate, setRate] = useState("");
  const [serviceFee, setServiceFee] = useState("0");
  const [insurance, setInsurance] = useState("0");
  const [result, setResult] = useState<CdasMaxLoanResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);
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

  async function calculate() {
    const months = Number(term);
    const annualRate = Number(rate);
    const monthlyFee = Number(serviceFee || 0);
    const insurancePercent = Number(insurance || 0);

    if (!opportunityId) {
      setError("Select a saved CDAS opportunity first.");
      return;
    }
    if (!Number.isInteger(months) || months <= 0 || !Number.isFinite(annualRate) || annualRate < 0 || !Number.isFinite(monthlyFee) || monthlyFee < 0 || !Number.isFinite(insurancePercent) || insurancePercent < 0) {
      setError("Enter a valid term, annual interest rate, service fee and insurance percentage.");
      return;
    }

    setCalculating(true);
    setError("");
    try {
      setResult(await cdasBookingApi.calculateMaxLoan({
        opportunity_id: opportunityId,
        term_months: months,
        annual_interest_rate: annualRate,
        monthly_service_fee: monthlyFee,
        insurance_percent: insurancePercent,
      }));
    } catch {
      setResult(null);
      setError("The maximum loan amount could not be calculated from this saved CDAS opportunity.");
    } finally {
      setCalculating(false);
    }
  }

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border bg-muted/40 p-2"><Calculator className="h-5 w-5"/></div>
            <div><CardTitle>CDAS Maximum Loan Amount Calculator</CardTitle><CardDescription>Convert a saved CDAS monthly deduction capacity into the maximum principal that fits a selected term, interest rate, service fee and financed insurance percentage.</CardDescription></div>
          </div>
          <Button variant="outline" size="sm" onClick={() => void loadOpportunities()} disabled={loading}><RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}/>Refresh</Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        {!loading && !opportunities.length ? <div className="rounded-lg border p-6 text-center text-sm text-muted-foreground">Save a CDAS booking opportunity first, then return here to calculate capacity.</div> : <>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="max-loan-opportunity">Saved CDAS opportunity</label>
            <select id="max-loan-opportunity" className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={opportunityId} onChange={(event) => { setOpportunityId(event.target.value); setResult(null); }}>
              {opportunities.map((item) => <option key={item.id} value={item.id}>{item.client_name || item.client_reference || "CDAS client"} — {item.opportunity_agency_name || "Agency not captured"}</option>)}
            </select>
          </div>

          {selected && <div className="grid gap-3 rounded-lg border bg-muted/20 p-4 text-sm sm:grid-cols-3">
            <div><div className="text-xs text-muted-foreground">Client</div><div className="font-medium">{selected.client_name || selected.client_reference || "CDAS client"}</div></div>
            <div><div className="text-xs text-muted-foreground">Agency</div><div className="font-medium">{selected.opportunity_agency_name || "Not captured"}</div></div>
            <div><div className="text-xs text-muted-foreground">Saved opportunity deduction</div><div className="font-medium">{money(selected.opportunity_deduction_amount)}</div></div>
          </div>}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="max-term">Term (months)</label><Input id="max-term" type="number" min="1" max="240" step="1" value={term} onChange={(event) => setTerm(event.target.value)}/></div>
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="max-rate">Annual interest rate (%)</label><Input id="max-rate" type="number" min="0" max="500" step="0.01" value={rate} onChange={(event) => setRate(event.target.value)} placeholder="e.g. 24"/></div>
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="service-fee">Monthly service fee</label><Input id="service-fee" type="number" min="0" step="0.01" value={serviceFee} onChange={(event) => setServiceFee(event.target.value)}/></div>
            <div className="space-y-2"><label className="text-sm font-medium" htmlFor="insurance-percent">Financed insurance (%)</label><Input id="insurance-percent" type="number" min="0" max="500" step="0.01" value={insurance} onChange={(event) => setInsurance(event.target.value)}/></div>
          </div>

          <Button type="button" onClick={() => void calculate()} disabled={calculating || loading}><Calculator className="mr-2 h-4 w-4"/>{calculating ? "Calculating..." : "Calculate maximum loan"}</Button>
        </>}
      </CardContent>
    </Card>

    {result && <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div><CardTitle>{result.client_name || result.client_reference || "CDAS client"}</CardTitle><CardDescription>Maximum principal estimate from the saved CDAS deduction capacity.</CardDescription></div>
          <div className="flex flex-wrap gap-2"><Badge variant={result.status === "CALCULATED" ? "default" : "secondary"}>{result.status.replaceAll("_", " ")}</Badge><Badge variant="outline">Confidence: {result.confidence.replaceAll("_", " ")}</Badge></div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-xl border bg-muted/20 p-5"><div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Maximum principal</div><div className="mt-1 text-3xl font-bold">{money(result.max_principal)}</div></div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Available CDAS capacity</div><div className="mt-1 font-semibold">{money(result.available_deduction_capacity)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Installment budget</div><div className="mt-1 font-semibold">{money(result.installment_budget)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Financed balance</div><div className="mt-1 font-semibold">{money(result.max_financed_balance)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Insurance amount</div><div className="mt-1 font-semibold">{money(result.insurance_amount)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Monthly total</div><div className="mt-1 font-semibold">{money(result.projected_monthly_total)}</div></div>
        </div>

        <div className="rounded-lg border p-4 text-sm"><div className="font-medium">Calculation inputs</div><div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"><span>{result.inputs.term_months} months</span><span>{result.inputs.annual_interest_rate}% annual rate</span><span>{money(result.inputs.monthly_service_fee)} monthly service fee</span><span>{result.inputs.insurance_percent}% financed insurance</span></div></div>
        {!!result.warnings.length && <div className="space-y-2">{result.warnings.map((warning) => <div key={warning} className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-sm">{warning}</div>)}</div>}
        <div className="rounded-md bg-muted/30 p-3 text-xs text-muted-foreground">{result.calculation_note}</div>
      </CardContent>
    </Card>}
  </div>;
}
