"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChartNoAxesCombined,
  CheckCircle2,
  Download,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import {
  createPortfolioRiskSnapshot,
  downloadPortfolioRiskCsv,
  getPortfolioRiskHistory,
  getPortfolioRiskOverview,
  type PortfolioRiskHistory,
  type PortfolioRiskOverview,
  type RiskGroup,
} from "@/api/portfolioRisk";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatMoney, titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Portfolio risk intelligence could not be loaded.";
}

function riskTone(value: number) {
  if (value >= 20) return "destructive" as const;
  if (value >= 8) return "outline" as const;
  return "secondary" as const;
}

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <Card><CardHeader className="pb-2"><CardDescription>{label}</CardDescription><CardTitle className="text-xl">{value}</CardTitle>{detail ? <p className="text-xs text-muted-foreground">{detail}</p> : null}</CardHeader></Card>;
}

function GroupTable({ title, description, rows }: { title: string; description: string; rows: RiskGroup[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader>
      <CardContent>
        <div className="overflow-x-auto rounded-2xl border">
          <Table>
            <TableHeader><TableRow><TableHead>Segment</TableHead><TableHead>Loans</TableHead><TableHead>Exposure</TableHead><TableHead>Share</TableHead><TableHead>PAR 30</TableHead><TableHead>FPD</TableHead></TableRow></TableHeader>
            <TableBody>
              {rows.slice(0, 12).map((row) => <TableRow key={row.label}><TableCell className="font-bold">{row.label}</TableCell><TableCell>{row.loan_count}</TableCell><TableCell>{formatMoney(row.exposure)}</TableCell><TableCell>{row.share_percent.toFixed(2)}%</TableCell><TableCell><Badge variant={riskTone(row.par_30)}>{row.par_30.toFixed(2)}%</Badge></TableCell><TableCell>{row.fpd_rate.toFixed(2)}%</TableCell></TableRow>)}
              {!rows.length ? <TableRow><TableCell colSpan={6} className="h-24 text-center text-muted-foreground">No exposure in this segment.</TableCell></TableRow> : null}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

export default function PortfolioRiskPage() {
  const [overview, setOverview] = useState<PortfolioRiskOverview | null>(null);
  const [history, setHistory] = useState<PortfolioRiskHistory>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextOverview, nextHistory] = await Promise.all([
        getPortfolioRiskOverview(),
        getPortfolioRiskHistory(),
      ]);
      setOverview(nextOverview);
      setHistory(nextHistory);
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function refreshSnapshot() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await createPortfolioRiskSnapshot();
      setNotice(`Risk snapshot ${result.run_reference} refreshed for ${result.loan_count} loan(s).`);
      await load();
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(false);
    }
  }

  const trend = useMemo(() => {
    if (history.length < 2) return null;
    const previous = history[history.length - 2];
    const current = history[history.length - 1];
    return { par30: current.par_30 - previous.par_30, exposure: current.active_exposure - previous.active_exposure };
  }, [history]);

  return (
    <div className="space-y-6 pb-12">
      <section className="overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground"><ChartNoAxesCombined className="h-4 w-4 text-primary" /> Portfolio Risk Intelligence</div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">See where the portfolio is heading</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">PAR 1/7/30/60/90, first-payment default, roll and cure rates, vintages, top-up performance, write-offs, concentration, employer/product/branch risk and six-month contractual cash flow from the live loan book.</p>
          </div>
          <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void downloadPortfolioRiskCsv()} disabled={!overview}><Download className="mr-2 h-4 w-4" /> Export CSV</Button><Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button><Button onClick={() => void refreshSnapshot()} disabled={busy}><Sparkles className="mr-2 h-4 w-4" /> Refresh risk snapshot</Button></div>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}
      {notice ? <div className="rounded-2xl border border-primary/25 bg-primary/5 p-4 text-sm font-bold">{notice}</div> : null}

      {overview ? <>
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Metric label="Active exposure" value={formatMoney(overview.summary.active_exposure)} detail={`${overview.summary.active_loans} active loans`} />
          <Metric label="PAR 30" value={`${overview.summary.par_30.toFixed(2)}%`} detail={`${formatMoney(overview.summary.par_30_amount)} exposure`} />
          <Metric label="First-payment default" value={`${overview.summary.fpd_rate.toFixed(2)}%`} detail={`${overview.summary.fpd_loans} FPD loan(s)`} />
          <Metric label="Write-off exposure" value={formatMoney(overview.summary.write_off_amount)} detail={`${overview.summary.write_off_count} explicit write-off case(s)`} />
          <Metric label="Projected next month" value={formatMoney(overview.projected_cash_flow[0]?.scheduled_collections ?? 0)} detail={`${formatMoney(overview.projected_cash_flow[0]?.cdas_scheduled ?? 0)} via CDAS`} />
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {[1, 7, 30, 60, 90].map((threshold) => {
            const key = `par_${threshold}` as keyof typeof overview.summary;
            const amountKey = `par_${threshold}_amount` as keyof typeof overview.summary;
            return <Card key={threshold}><CardHeader className="pb-2"><CardDescription>PAR {threshold}</CardDescription><CardTitle className="flex items-center gap-2"><Badge variant={riskTone(Number(overview.summary[key]))}>{Number(overview.summary[key]).toFixed(2)}%</Badge></CardTitle><p className="text-xs text-muted-foreground">{formatMoney(Number(overview.summary[amountKey]))}</p></CardHeader></Card>;
          })}
        </section>

        <Card className={overview.roll_and_cure.available ? "" : "border-amber-500/30"}>
          <CardHeader><CardTitle className="flex items-center gap-2">{overview.roll_and_cure.available ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : <AlertTriangle className="h-5 w-5 text-amber-500" />} Roll & cure movement</CardTitle><CardDescription>{overview.roll_and_cure.available ? `Measured across ${overview.roll_and_cure.interval_days} day(s), from ${overview.roll_and_cure.previous_snapshot_date} to ${overview.roll_and_cure.current_snapshot_date}.` : overview.roll_and_cure.message}</CardDescription></CardHeader>
          {overview.roll_and_cure.available ? <CardContent><div className="grid gap-3 md:grid-cols-2"><div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Cure rate</p><p className="mt-2 flex items-center gap-2 text-2xl font-black"><TrendingDown className="h-5 w-5 text-emerald-600" />{(overview.roll_and_cure.cure_rate ?? 0).toFixed(2)}%</p></div><div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Roll-forward rate</p><p className="mt-2 flex items-center gap-2 text-2xl font-black"><TrendingUp className="h-5 w-5 text-amber-500" />{(overview.roll_and_cure.roll_forward_rate ?? 0).toFixed(2)}%</p></div></div></CardContent> : null}
        </Card>

        <section className="grid gap-6 xl:grid-cols-2">
          <Card><CardHeader><CardTitle>Delinquency buckets</CardTitle><CardDescription>Current exposure distribution by days past due.</CardDescription></CardHeader><CardContent><div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Bucket</TableHead><TableHead>Loans</TableHead><TableHead>Exposure</TableHead></TableRow></TableHeader><TableBody>{overview.delinquency_buckets.map((row) => <TableRow key={row.bucket}><TableCell className="font-bold">{row.bucket === "current" ? "Current" : `${row.bucket} days`}</TableCell><TableCell>{row.loan_count}</TableCell><TableCell>{formatMoney(row.exposure)}</TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card>
          <Card><CardHeader><CardTitle>Projected contractual cash flow</CardTitle><CardDescription>Remaining scheduled installments for the next six months. This is not a guarantee of collection.</CardDescription></CardHeader><CardContent><div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Month</TableHead><TableHead>Scheduled</TableHead><TableHead>CDAS</TableHead><TableHead>Other</TableHead></TableRow></TableHeader><TableBody>{overview.projected_cash_flow.map((row) => <TableRow key={row.month}><TableCell className="font-bold">{row.month}</TableCell><TableCell>{formatMoney(row.scheduled_collections)}</TableCell><TableCell>{formatMoney(row.cdas_scheduled)}</TableCell><TableCell>{formatMoney(row.non_cdas_scheduled)}</TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card>
        </section>

        <Card><CardHeader><CardTitle>Vintage / cohort performance</CardTitle><CardDescription>Current quality of loans grouped by origination month.</CardDescription></CardHeader><CardContent><div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Vintage</TableHead><TableHead>Loans</TableHead><TableHead>Originated</TableHead><TableHead>Outstanding</TableHead><TableHead>PAR 30</TableHead><TableHead>FPD</TableHead><TableHead>Write-offs</TableHead><TableHead>Top-ups</TableHead></TableRow></TableHeader><TableBody>{overview.vintages.map((row) => <TableRow key={row.vintage}><TableCell className="font-bold">{row.vintage}</TableCell><TableCell>{row.loan_count}</TableCell><TableCell>{formatMoney(row.originated_principal)}</TableCell><TableCell>{formatMoney(row.outstanding_balance)}</TableCell><TableCell><Badge variant={riskTone(row.par_30)}>{row.par_30.toFixed(2)}%</Badge></TableCell><TableCell>{row.fpd_rate.toFixed(2)}%</TableCell><TableCell>{row.write_off_count}</TableCell><TableCell>{row.top_up_count}</TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card>

        <section className="grid gap-6 xl:grid-cols-3"><GroupTable title="Branch risk" description="Exposure, PAR 30 and FPD by branch." rows={overview.branch_risk} /><GroupTable title="Product risk" description="Product-specific risk where a product is mapped; calculation method is used as a transparent fallback." rows={overview.product_risk} /><GroupTable title="Employer risk" description="Employer/work-group concentration and repayment quality." rows={overview.employer_risk} /></section>

        <section className="grid gap-4 md:grid-cols-3">
          {(["branch", "product", "employer"] as const).map((dimension) => { const item = overview.concentration[dimension]; return <Card key={dimension}><CardHeader><CardDescription>{titleCase(dimension)} concentration</CardDescription><CardTitle>{item.top_share_percent.toFixed(2)}% top share</CardTitle><p className="text-xs text-muted-foreground">HHI {item.hhi.toFixed(0)} · {item.group_count} group(s)</p></CardHeader></Card>; })}
        </section>

        <Card><CardHeader><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /> Methodology & evidence rules</CardTitle><CardDescription>LoanHub distinguishes measurements from assumptions. Historical roll/cure figures only appear after evidence snapshots exist.</CardDescription></CardHeader><CardContent className="grid gap-3 md:grid-cols-2">{Object.entries(overview.methodology).map(([key, value]) => <div key={key} className="rounded-2xl border p-4"><p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{titleCase(key)}</p><p className="mt-2 text-sm leading-6">{value}</p></div>)}</CardContent></Card>
      </> : null}
    </div>
  );
}
