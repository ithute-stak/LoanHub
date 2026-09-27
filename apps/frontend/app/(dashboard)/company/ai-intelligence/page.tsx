"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import {
  getAIIntelligenceInsights,
  getAIIntelligenceOverview,
  reviewAIInsight,
  runAIIntelligence,
  type AIIntelligenceInsight,
  type AIIntelligenceOverview,
} from "@/api/aiIntelligence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "AI intelligence data could not be loaded.";
}

function severityVariant(value: string) {
  if (value === "critical" || value === "high") return "destructive" as const;
  if (value === "medium") return "outline" as const;
  return "secondary" as const;
}

export default function AIIntelligencePage() {
  const [overview, setOverview] = useState<AIIntelligenceOverview | null>(null);
  const [insights, setInsights] = useState<AIIntelligenceInsight[]>([]);
  const [domain, setDomain] = useState("all");
  const [severity, setSeverity] = useState("all");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextOverview, nextInsights] = await Promise.all([
        getAIIntelligenceOverview(),
        getAIIntelligenceInsights({ status: "open" }),
      ]);
      setOverview(nextOverview);
      setInsights(nextInsights);
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const filtered = useMemo(() => insights.filter((row) => (
    (domain === "all" || row.domain === domain)
    && (severity === "all" || row.severity === severity)
  )), [domain, insights, severity]);

  async function run() {
    setBusy("run");
    setError(null);
    try {
      await runAIIntelligence();
      await load();
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  async function review(row: AIIntelligenceInsight, status: "reviewed" | "dismissed" | "actioned") {
    setBusy(row.id);
    setError(null);
    try {
      await reviewAIInsight(row.id, {
        status,
        feedback: status === "actioned" ? "actioned" : status === "dismissed" ? "dismissed" : "useful",
      });
      await load();
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6 pb-12">
      <section className="overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground">
              <BrainCircuit className="h-4 w-4 text-primary" /> LoanHub AI Intelligence
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Explainable operational intelligence</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">
              Surface underwriting, portfolio-risk and collections signals from LoanHub evidence. Every insight shows its rationale and remains advisory: people keep control of approvals, disbursements and recovery actions.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
            <Button onClick={() => void run()} disabled={busy === "run"}><Sparkles className="mr-2 h-4 w-4" /> {busy === "run" ? "Analysing..." : "Run intelligence"}</Button>
          </div>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Card><CardHeader className="pb-2"><CardDescription>Open insights</CardDescription><CardTitle>{overview?.open_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Critical</CardDescription><CardTitle className="text-destructive">{overview?.critical_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>High</CardDescription><CardTitle>{overview?.high_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Latest run</CardDescription><CardTitle className="text-base">{overview?.latest_run?.run_reference ?? "Not run yet"}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Model</CardDescription><CardTitle className="text-base">{overview?.latest_run?.model_version ?? "explainable-v1"}</CardTitle></CardHeader></Card>
      </section>

      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-5 w-5 text-emerald-600" /> Human-control guardrail</CardTitle><CardDescription>LoanHub AI is decision support only. It cannot approve credit, waive committee controls, disburse money or automatically close collection actions.</CardDescription></CardHeader>
      </Card>

      <Card>
        <CardHeader className="gap-4 md:flex-row md:items-end md:justify-between">
          <div><CardTitle>Prioritised intelligence queue</CardTitle><CardDescription>Review why each signal was produced, then accept, action or dismiss it with a human audit trail.</CardDescription></div>
          <div className="flex w-full gap-2 md:w-auto">
            <Select value={domain} onValueChange={setDomain}><SelectTrigger className="w-[180px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All domains</SelectItem><SelectItem value="underwriting">Underwriting</SelectItem><SelectItem value="portfolio_risk">Portfolio risk</SelectItem><SelectItem value="collections">Collections</SelectItem></SelectContent></Select>
            <Select value={severity} onValueChange={setSeverity}><SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All severity</SelectItem><SelectItem value="critical">Critical</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="low">Low</SelectItem></SelectContent></Select>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {filtered.map((row) => (
            <div key={row.id} className="rounded-2xl border p-4 md:p-5">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><Badge variant={severityVariant(row.severity)}>{titleCase(row.severity)}</Badge><Badge variant="outline">{titleCase(row.domain)}</Badge><span className="text-xs font-bold text-muted-foreground">Confidence {row.confidence_percent.toFixed(0)}%</span>{row.folio_number ? <span className="font-mono text-xs font-black text-primary">{row.folio_number}</span> : null}</div>
                  <h3 className="mt-3 text-lg font-black">{row.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{row.explanation}</p>
                  <div className="mt-3 rounded-xl bg-muted/50 p-3 text-sm"><p className="font-black">Recommended human action</p><p className="mt-1 text-muted-foreground">{row.recommended_action}</p></div>
                  {row.rationale.length ? <div className="mt-3"><p className="text-xs font-black uppercase tracking-wide text-muted-foreground">Why this appeared</p><ul className="mt-2 space-y-1 text-sm text-muted-foreground">{row.rationale.map((reason) => <li key={reason} className="flex gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{reason}</li>)}</ul></div> : null}
                </div>
                <div className="flex shrink-0 flex-wrap gap-2"><Button size="sm" variant="outline" disabled={busy === row.id} onClick={() => void review(row, "reviewed")}><CheckCircle2 className="mr-2 h-4 w-4" /> Reviewed</Button><Button size="sm" variant="outline" disabled={busy === row.id} onClick={() => void review(row, "dismissed")}>Dismiss</Button><Button size="sm" disabled={busy === row.id} onClick={() => void review(row, "actioned")}>Mark actioned</Button></div>
              </div>
            </div>
          ))}
          {!loading && !filtered.length ? <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">No open intelligence signals match the selected filters.</div> : null}
        </CardContent>
      </Card>
    </div>
  );
}
