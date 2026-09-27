"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  CalendarRange,
  RefreshCcw,
  ShieldCheck,
  TrendingDown,
  WalletCards,
} from "lucide-react";

import {
  getPredictiveOverview,
  runPredictiveIntelligence,
  type PredictiveOverview,
  type PredictiveSignal,
} from "@/api/predictiveIntelligence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatMoney, titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (typeof response?.data?.detail === "string") return response.data.detail;
  }
  return error instanceof Error ? error.message : "Predictive intelligence could not be loaded.";
}

function riskVariant(value: string) {
  if (value === "critical" || value === "high") return "destructive" as const;
  if (value === "elevated" || value === "watch") return "outline" as const;
  return "secondary" as const;
}

export default function PredictiveIntelligencePage() {
  const [overview, setOverview] = useState<PredictiveOverview | null>(null);
  const [band, setBand] = useState("all");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setOverview(await getPredictiveOverview());
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const signals = useMemo(() => (
    (overview?.signals ?? []).filter((row) => band === "all" || row.risk_band === band)
  ), [band, overview?.signals]);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      await runPredictiveIntelligence();
      await load();
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setRunning(false);
    }
  }

  const latest = overview?.latest_run;
  const hasCollectionHistory = (overview?.cashflow?.[0]?.history_installment_count ?? 0) > 0;

  return (
    <div className="space-y-6 pb-12">
      <section className="overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground">
              <BrainCircuit className="h-4 w-4 text-primary" /> Predictive Intelligence
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">See portfolio pressure before it becomes a surprise</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">
              Forecast near-term collection cash, surface loans trending toward deeper delinquency, and identify possible PAR30 entry using stored LoanHub evidence. Forecasts are transparent decision support, not automated credit or collection decisions.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
            <Button onClick={() => void run()} disabled={running}><Activity className="mr-2 h-4 w-4" /> {running ? "Forecasting..." : "Run forecast"}</Button>
          </div>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <Card><CardHeader className="pb-2"><CardDescription>Loans assessed</CardDescription><CardTitle>{latest?.loan_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Possible PAR30 entry</CardDescription><CardTitle>{latest?.projected_par30_entry_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>High / critical</CardDescription><CardTitle>{(latest?.high_count ?? 0) + (latest?.critical_count ?? 0)}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>High-risk exposure</CardDescription><CardTitle className="text-lg">{formatMoney(overview?.high_risk_exposure ?? 0)}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Observed collection rate</CardDescription><CardTitle>{!latest ? "—" : hasCollectionHistory ? `${(latest.observed_collection_rate * 100).toFixed(1)}%` : "No history"}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Evidence date</CardDescription><CardTitle className="text-base">{latest?.source_snapshot_date ?? "Not run"}</CardTitle></CardHeader></Card>
      </section>

      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-5 w-5 text-emerald-600" /> Forecast guardrail</CardTitle><CardDescription>The score is a transparent early-warning score, not a calibrated default probability. LoanHub does not use it to approve/decline credit, move money, or automatically start collection actions.</CardDescription></CardHeader>
      </Card>

      <section className="grid gap-4 lg:grid-cols-3">
        {(overview?.cashflow ?? []).map((row) => (
          <Card key={row.id}>
            <CardHeader><CardTitle className="flex items-center gap-2"><CalendarRange className="h-5 w-5 text-primary" /> Next {row.horizon_days} days</CardTitle><CardDescription>{titleCase(row.confidence_band)} confidence · {row.due_installment_count} scheduled installment(s)</CardDescription></CardHeader>
            <CardContent className="space-y-3">
              <div><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Contractual due</p><p className="text-xl font-black">{formatMoney(row.contractual_due)}</p></div>
              <div><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Evidence-adjusted collection outlook</p><p className="text-xl font-black text-primary">{formatMoney(row.expected_collection)}</p></div>
              {row.history_installment_count > 0 ? (
                <p className="text-xs leading-5 text-muted-foreground">Based on the observed {Math.round(row.observed_collection_rate * 1000) / 10}% collection rate over {row.history_installment_count} historical installment(s). It is a forecast, not a guarantee.</p>
              ) : (
                <p className="text-xs leading-5 text-muted-foreground">No repayment history was available in the 90-day lookback. LoanHub therefore shows contractual due as the outlook and marks confidence low instead of inventing a collection rate.</p>
              )}
            </CardContent>
          </Card>
        ))}
        {!overview?.cashflow.length ? <Card className="lg:col-span-3"><CardContent className="p-8 text-center text-sm text-muted-foreground">Run Predictive Intelligence to create the 30/60/90-day collection outlook.</CardContent></Card> : null}
      </section>

      <Card>
        <CardHeader className="gap-4 md:flex-row md:items-end md:justify-between">
          <div><CardTitle className="flex items-center gap-2"><TrendingDown className="h-5 w-5 text-primary" /> Loan early-warning register</CardTitle><CardDescription>Signals are generated from current DPD, stored DPD movement, first-payment-default evidence, top-up stress and existing collection priority.</CardDescription></div>
          <Select value={band} onValueChange={setBand}><SelectTrigger className="w-full md:w-[180px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All risk bands</SelectItem><SelectItem value="critical">Critical</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="elevated">Elevated</SelectItem><SelectItem value="watch">Watch</SelectItem><SelectItem value="stable">Stable</SelectItem></SelectContent></Select>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-2xl border">
            <Table>
              <TableHeader><TableRow><TableHead>Folio</TableHead><TableHead>Risk</TableHead><TableHead>DPD movement</TableHead><TableHead>30-day stress scenario</TableHead><TableHead>Exposure</TableHead><TableHead>Why</TableHead><TableHead>Human action</TableHead></TableRow></TableHeader>
              <TableBody>
                {signals.map((row: PredictiveSignal) => (
                  <TableRow key={row.id}>
                    <TableCell><p className="font-mono font-black text-primary">{row.folio_number}</p><p className="text-[11px] text-muted-foreground">{row.loan_reference || "—"}</p></TableCell>
                    <TableCell><Badge variant={riskVariant(row.risk_band)}>{titleCase(row.risk_band)} · {row.risk_score.toFixed(0)}</Badge>{row.projected_par30_entry ? <p className="mt-2 flex items-center gap-1 text-xs font-bold text-amber-600"><AlertTriangle className="h-3.5 w-3.5" /> PAR30 watch</p> : null}</TableCell>
                    <TableCell><p className="font-bold">{row.current_dpd} DPD</p><p className="text-xs text-muted-foreground">{row.previous_dpd === null ? "No prior snapshot" : `${row.previous_dpd} → ${row.current_dpd} (${row.dpd_change && row.dpd_change > 0 ? "+" : ""}${row.dpd_change ?? 0})`}</p></TableCell>
                    <TableCell><p className="font-bold">{row.stress_bucket_30d}</p><p className="text-xs text-muted-foreground">If current delinquency remains uncured for 30 days</p></TableCell>
                    <TableCell className="font-bold">{formatMoney(row.outstanding_balance)}</TableCell>
                    <TableCell className="min-w-[260px]"><ul className="space-y-1 text-xs text-muted-foreground">{row.rationale.length ? row.rationale.map((reason) => <li key={reason}>• {reason}</li>) : <li>• No escalation factor detected</li>}</ul></TableCell>
                    <TableCell className="min-w-[280px] text-xs text-muted-foreground">{row.recommended_action}</TableCell>
                  </TableRow>
                ))}
                {!loading && !signals.length ? <TableRow><TableCell colSpan={7} className="h-28 text-center text-muted-foreground">No predictive signals match the selected risk band.</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><WalletCards className="h-5 w-5 text-primary" /> Forecast method</CardTitle><CardDescription>Collection outlook uses scheduled unpaid installment amounts and the observed collection rate from the preceding 90 days. With insufficient history, LoanHub shows contractual cash flow and marks confidence low instead of inventing a performance rate.</CardDescription></CardHeader>
      </Card>
    </div>
  );
}
