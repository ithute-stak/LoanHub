"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, CheckCircle2, Gauge, RefreshCcw, Sparkles } from "lucide-react";

import { analyticsApi, type ManagementCommandIntelligence } from "@/api/analytics";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMoney, titleCase } from "@/lib/format";

function isoDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

function metricValue(metric?: { value: number; format: "money" | "integer" | "percent" | "decimal" }) {
  if (!metric) return "—";
  if (metric.format === "money") return formatMoney(metric.value);
  if (metric.format === "percent") return `${metric.value.toFixed(2)}%`;
  if (metric.format === "integer") return Math.round(metric.value).toLocaleString();
  return metric.value.toFixed(2);
}

function severityVariant(severity: string) {
  if (severity === "critical") return "destructive" as const;
  if (severity === "high") return "outline" as const;
  return "secondary" as const;
}

export function ManagementCommandIntelligencePanel() {
  const today = useMemo(() => new Date(), []);
  const start = useMemo(() => {
    const value = new Date(today);
    value.setDate(value.getDate() - 29);
    return value;
  }, [today]);

  const [data, setData] = useState<ManagementCommandIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await analyticsApi.command({
        date_from: isoDate(start),
        date_to: isoDate(today),
        granularity: "day",
      });
      setData(result);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Management command intelligence could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [start, today]);

  useEffect(() => { void load(); }, [load]);

  return (
    <section className="space-y-4">
      <Card className={data?.command_status === "critical" ? "border-destructive/50" : data?.command_status === "high" ? "border-amber-500/40" : ""}>
        <CardHeader>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs font-black text-muted-foreground"><Gauge className="h-4 w-4 text-primary" /> Management Command Intelligence</div>
              <CardTitle className="mt-3 text-2xl">What needs management attention first</CardTitle>
              <CardDescription className="mt-2 max-w-4xl">Evidence-backed priorities across lending, collections, finance, treasury, branches, audit and operations. Recommendations require human review and do not execute high-impact actions automatically.</CardDescription>
            </div>
            <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh priorities</Button>
          </div>
        </CardHeader>
        {error ? <CardContent><div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div></CardContent> : null}
        {data ? <CardContent className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Command status</p><div className="mt-2"><Badge variant={severityVariant(data.command_status)}>{titleCase(data.command_status)}</Badge></div></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Enterprise risk</p><p className="mt-2 text-2xl font-black">{data.enterprise_risk_score}/100</p><p className="text-xs text-muted-foreground">{titleCase(data.enterprise_risk_level)}</p></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Critical</p><p className="mt-2 text-2xl font-black">{data.priority_counts.critical}</p></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">High</p><p className="mt-2 text-2xl font-black">{data.priority_counts.high}</p></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Medium</p><p className="mt-2 text-2xl font-black">{data.priority_counts.medium}</p></div>
            <div className="rounded-2xl border p-4"><p className="text-xs font-black uppercase text-muted-foreground">Open priorities</p><p className="mt-2 text-2xl font-black">{data.priority_counts.total}</p></div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {["outstanding_balance", "collections", "net_cashflow", "collection_rate"].map((key) => {
              const metric = data.executive_metrics[key];
              return <div key={key} className="rounded-2xl border bg-card p-4"><p className="text-xs font-black uppercase text-muted-foreground">{metric?.label ?? titleCase(key)}</p><p className="mt-2 text-xl font-black">{metricValue(metric)}</p>{metric?.change_percent != null ? <p className="mt-1 text-xs text-muted-foreground">{metric.change_percent >= 0 ? "+" : ""}{metric.change_percent.toFixed(1)}% vs prior period</p> : null}</div>;
            })}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3"><h3 className="text-lg font-black">Ranked management action queue</h3><span className="text-xs text-muted-foreground">Highest severity first</span></div>
            {data.priority_actions.length ? data.priority_actions.map((item) => (
              <div key={item.id} className="rounded-2xl border p-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border bg-background text-sm font-black">{item.rank}</div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2"><p className="font-black">{item.title}</p><Badge variant={severityVariant(item.severity)}>{titleCase(item.severity)}</Badge><Badge variant="secondary">{titleCase(item.domain)}</Badge></div>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.why_now}</p>
                      <div className="mt-3 rounded-xl bg-muted/40 p-3"><p className="text-xs font-black uppercase tracking-wide text-muted-foreground">Recommended management action</p><p className="mt-1 text-sm">{item.recommended_action}</p></div>
                    </div>
                  </div>
                  <Button asChild variant="outline" className="shrink-0"><Link href={item.action_url}>Open evidence <ArrowRight className="ml-2 h-4 w-4" /></Link></Button>
                </div>
              </div>
            )) : <div className="rounded-2xl border bg-emerald-500/5 p-4 text-sm font-bold"><CheckCircle2 className="mr-2 inline h-4 w-4" />No management priority thresholds are currently breached.</div>}
          </div>

          {data.opportunities.length ? <div className="space-y-3">
            <h3 className="flex items-center gap-2 text-lg font-black"><Sparkles className="h-5 w-5 text-primary" />Evidence-backed opportunities</h3>
            <div className="grid gap-3 md:grid-cols-2">{data.opportunities.map((item) => <div key={item.code} className="rounded-2xl border p-4"><p className="font-black">{item.title}</p><p className="mt-2 text-sm leading-6 text-muted-foreground">{item.management_option}</p><Button asChild variant="link" className="mt-2 h-auto p-0"><Link href={item.action_url}>Review supporting area <ArrowRight className="ml-1 h-4 w-4" /></Link></Button></div>)}</div>
          </div> : null}

          <div className="rounded-2xl border bg-muted/30 p-4 text-sm text-muted-foreground"><AlertTriangle className="mr-2 inline h-4 w-4" />{data.policy_note}</div>
        </CardContent> : null}
      </Card>
    </section>
  );
}
