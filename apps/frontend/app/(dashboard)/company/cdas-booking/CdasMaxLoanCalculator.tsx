"use client";

import { useState } from "react";
import { Calculator } from "lucide-react";

import { cdasBookingApi } from "@/api/cdasBooking";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { CdasMaxLoanResult } from "@/types/cdasMaxLoan";

function money(value?: number | null) {
  if (value === null || value === undefined) return "Not available";
  return `M ${Number(value).toLocaleString("en-ZA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function CdasMaxLoanCalculator() {
  const [capacity, setCapacity] = useState("");
  const [term, setTerm] = useState("12");
  const [rate, setRate] = useState("");
  const [serviceFee, setServiceFee] = useState("0");
  const [insurance, setInsurance] = useState("0");
  const [result, setResult] = useState<CdasMaxLoanResult | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState("");

  async function calculate() {
    const monthlyCapacity = Number(capacity);
    const months = Number(term);
    const annualRate = Number(rate);
    const monthlyFee = Number(serviceFee || 0);
    const insurancePercent = Number(insurance || 0);

    if (!Number.isFinite(monthlyCapacity) || monthlyCapacity < 0 || !Number.isInteger(months) || months <= 0 || !Number.isFinite(annualRate) || annualRate < 0 || !Number.isFinite(monthlyFee) || monthlyFee < 0 || !Number.isFinite(insurancePercent) || insurancePercent < 0) {
      setError("Enter a valid monthly capacity, term, annual interest rate, service fee and insurance percentage.");
      return;
    }

    setCalculating(true);
    setError("");
    try {
      setResult(await cdasBookingApi.calculateMaxLoan({
        monthly_capacity: monthlyCapacity,
        term_months: months,
        annual_interest_rate: annualRate,
        monthly_service_fee: monthlyFee,
        insurance_percent: insurancePercent,
      }));
    } catch {
      setResult(null);
      setError("The reference calculation could not be completed. Check the entered values.");
    } finally {
      setCalculating(false);
    }
  }

  return <div className="space-y-5">
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="rounded-lg border bg-muted/40 p-2"><Calculator className="h-5 w-5"/></div>
          <div>
            <CardTitle>CDAS Loan Reference Calculator</CardTitle>
            <CardDescription>Manual arithmetic only. Enter a monthly capacity yourself, then compare terms, rates, service fees and financed insurance. This tool does not read a borrower record or make an approval or eligibility decision.</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {error && <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{error}</div>}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <div className="space-y-2"><label className="text-sm font-medium" htmlFor="manual-capacity">Monthly capacity</label><Input id="manual-capacity" type="number" min="0" step="0.01" value={capacity} onChange={(event) => setCapacity(event.target.value)} placeholder="Enter manually"/></div>
          <div className="space-y-2"><label className="text-sm font-medium" htmlFor="max-term">Term (months)</label><Input id="max-term" type="number" min="1" max="240" step="1" value={term} onChange={(event) => setTerm(event.target.value)}/></div>
          <div className="space-y-2"><label className="text-sm font-medium" htmlFor="max-rate">Annual interest rate (%)</label><Input id="max-rate" type="number" min="0" max="500" step="0.01" value={rate} onChange={(event) => setRate(event.target.value)} placeholder="e.g. 24"/></div>
          <div className="space-y-2"><label className="text-sm font-medium" htmlFor="service-fee">Monthly service fee</label><Input id="service-fee" type="number" min="0" step="0.01" value={serviceFee} onChange={(event) => setServiceFee(event.target.value)}/></div>
          <div className="space-y-2"><label className="text-sm font-medium" htmlFor="insurance-percent">Financed insurance (%)</label><Input id="insurance-percent" type="number" min="0" max="500" step="0.01" value={insurance} onChange={(event) => setInsurance(event.target.value)}/></div>
        </div>
        <Button type="button" onClick={() => void calculate()} disabled={calculating}><Calculator className="mr-2 h-4 w-4"/>{calculating ? "Calculating..." : "Calculate reference amount"}</Button>
      </CardContent>
    </Card>

    {result && <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div><CardTitle>Reference calculation</CardTitle><CardDescription>Transparent arithmetic from the values entered above.</CardDescription></div>
          <Badge variant={result.status === "CALCULATED" ? "default" : "secondary"}>{result.status.replaceAll("_", " ")}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-xl border bg-muted/20 p-5"><div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reference principal</div><div className="mt-1 text-3xl font-bold">{money(result.max_principal)}</div></div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Entered monthly capacity</div><div className="mt-1 font-semibold">{money(result.inputs.monthly_capacity)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Installment budget</div><div className="mt-1 font-semibold">{money(result.installment_budget)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Financed balance</div><div className="mt-1 font-semibold">{money(result.max_financed_balance)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Insurance amount</div><div className="mt-1 font-semibold">{money(result.insurance_amount)}</div></div>
          <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">Monthly total</div><div className="mt-1 font-semibold">{money(result.projected_monthly_total)}</div></div>
        </div>
        <div className="rounded-lg border p-4 text-sm"><div className="font-medium">Calculation inputs</div><div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"><span>{result.inputs.term_months} months</span><span>{result.inputs.annual_interest_rate}% annual rate</span><span>{money(result.inputs.monthly_service_fee)} monthly service fee</span><span>{result.inputs.insurance_percent}% financed insurance</span></div></div>
        <div className="rounded-md bg-muted/30 p-3 text-xs text-muted-foreground">{result.calculation_note}</div>
      </CardContent>
    </Card>}
  </div>;
}
