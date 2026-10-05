"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircuitBoard,
  Gauge,
  RefreshCcw,
  ServerCog,
  ShieldCheck,
  TimerReset,
} from "lucide-react";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type WorkerStatus = {
  name: string;
  configured: boolean;
  ready: boolean;
  detail?: string | null;
};

type WorkerMetric = {
  calls: number;
  successes: number;
  failures: number;
  fallbacks: number;
  parity_mismatches: number;
  consecutive_failures: number;
  circuit_open: boolean;
  circuit_retry_in_seconds: number;
  last_latency_ms?: number | null;
  last_error?: string | null;
};

type RuntimeStatus = {
  authority: string;
  frontend: string[];
  backend: string[];
  workers: WorkerStatus[];
  runtime_metrics: Record<string, WorkerMetric>;
  routing: Record<string, { mode: string; env: string }>;
  rules: Record<string, string>;
};

type BenchmarkResult = {
  workload: string;
  worker: string;
  iterations: number;
  successes: number;
  parity_passed: number;
  parity_failed: number;
  avg_latency_ms: number | null;
  max_latency_ms: number | null;
  routing_mode: string;
  promotion_candidate: boolean;
  recommendation: string;
};

type BenchmarkResponse = {
  iterations: number;
  non_authoritative: boolean;
  changes_routing: boolean;
  results: BenchmarkResult[];
};

const labels: Record<string, string> = {
  rust_compute: "Rust compute",
  go_worker: "Go worker",
  java_worker: "Java event worker",
};

function tone(ready: boolean, circuitOpen: boolean) {
  if (circuitOpen) return "border-red-300 bg-red-50/70";
  if (ready) return "border-emerald-300 bg-emerald-50/70";
  return "border-amber-300 bg-amber-50/70";
}

export default function RuntimeControlPage() {
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkResponse | null>(null);
  const [benchmarking, setBenchmarking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get<RuntimeStatus>("/runtime/workers/status");
      setStatus(response.data);
      setError(null);
    } catch (requestError: any) {
      const message = requestError?.response?.data?.detail ?? requestError?.message ?? "Could not load runtime status";
      setError(String(message));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  const healthy = useMemo(
    () => status?.workers.filter((worker) => worker.configured && worker.ready).length ?? 0,
    [status],
  );
  const configured = useMemo(
    () => status?.workers.filter((worker) => worker.configured).length ?? 0,
    [status],
  );

  const runBenchmark = useCallback(async () => {
    setBenchmarking(true);
    try {
      const response = await api.post<BenchmarkResponse>("/runtime/benchmarks/run?iterations=5");
      setBenchmark(response.data);
      setError(null);
    } catch (requestError: any) {
      const message = requestError?.response?.data?.detail ?? requestError?.message ?? "Could not run runtime benchmark";
      setError(String(message));
    } finally {
      setBenchmarking(false);
    }
  }, []);

  return (
    <main className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">Platform owner runtime control</p>
            <h1 className="mt-2 text-3xl font-black">Polyglot work-sharing monitor</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Observe Python authority, Rust compute, Go background work, Java enterprise events,
              C++ native kernels and browser Rust/WASM without allowing worker failure to stop LoanHub.
            </p>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            <RefreshCcw className={loading ? "animate-spin" : ""} />
            Refresh runtime
          </Button>
        </div>
      </section>

      {error ? (
        <div className="flex gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <div><p className="font-black">Runtime status unavailable</p><p>{error}</p></div>
        </div>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-3"><CardDescription>Authority</CardDescription><CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" />Python</CardTitle></CardHeader>
          <CardContent><p className="text-sm text-muted-foreground">Final lending, accounting, tenancy and provider-write authority.</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3"><CardDescription>Configured workers</CardDescription><CardTitle>{configured}</CardTitle></CardHeader>
          <CardContent><p className="text-sm text-muted-foreground">{healthy} currently ready.</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3"><CardDescription>Frontend runtime</CardDescription><CardTitle>Next.js + WASM</CardTitle></CardHeader>
          <CardContent><p className="text-sm text-muted-foreground">Browser previews are non-authoritative and parity checked.</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3"><CardDescription>Failure mode</CardDescription><CardTitle>Python fallback</CardTitle></CardHeader>
          <CardContent><p className="text-sm text-muted-foreground">Worker faults open circuits instead of blocking core lending.</p></CardContent>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-3">
        {(status?.workers ?? []).map((worker) => {
          const metric = status?.runtime_metrics?.[worker.name];
          const circuitOpen = Boolean(metric?.circuit_open);
          return (
            <Card key={worker.name} className={tone(worker.ready, circuitOpen)}>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle className="flex items-center gap-2"><ServerCog className="h-5 w-5" />{labels[worker.name] ?? worker.name}</CardTitle>
                    <CardDescription>{worker.detail || "Specialized LoanHub worker"}</CardDescription>
                  </div>
                  <Badge variant={worker.ready && !circuitOpen ? "default" : "secondary"}>
                    {circuitOpen ? "Circuit open" : worker.ready ? "Ready" : worker.configured ? "Unavailable" : "Disabled"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-xl bg-background/80 p-3"><p className="text-xs text-muted-foreground">Calls</p><p className="font-black">{metric?.calls ?? 0}</p></div>
                  <div className="rounded-xl bg-background/80 p-3"><p className="text-xs text-muted-foreground">Fallbacks</p><p className="font-black">{metric?.fallbacks ?? 0}</p></div>
                  <div className="rounded-xl bg-background/80 p-3"><p className="text-xs text-muted-foreground">Failures</p><p className="font-black">{metric?.failures ?? 0}</p></div>
                  <div className="rounded-xl bg-background/80 p-3"><p className="text-xs text-muted-foreground">Parity mismatches</p><p className="font-black">{metric?.parity_mismatches ?? 0}</p></div>
                </div>

                <div className="space-y-2 rounded-2xl border bg-background/80 p-4 text-sm">
                  <div className="flex items-center justify-between gap-2"><span className="flex items-center gap-2 text-muted-foreground"><Gauge className="h-4 w-4" />Last latency</span><strong>{metric?.last_latency_ms == null ? "—" : `${metric.last_latency_ms} ms`}</strong></div>
                  <div className="flex items-center justify-between gap-2"><span className="flex items-center gap-2 text-muted-foreground"><TimerReset className="h-4 w-4" />Retry in</span><strong>{circuitOpen ? `${metric?.circuit_retry_in_seconds ?? 0}s` : "Ready"}</strong></div>
                  <div className="flex items-center justify-between gap-2"><span className="flex items-center gap-2 text-muted-foreground"><Activity className="h-4 w-4" />Consecutive failures</span><strong>{metric?.consecutive_failures ?? 0}</strong></div>
                </div>

                {metric?.last_error ? <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800">{metric.last_error}</p> : null}
              </CardContent>
            </Card>
          );
        })}
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5 text-primary" />Promotion benchmark</CardTitle>
              <CardDescription>Run five read-only parity and latency checks before promoting a worker workload.</CardDescription>
            </div>
            <Button variant="outline" onClick={() => void runBenchmark()} disabled={benchmarking}>
              <Gauge className={benchmarking ? "animate-pulse" : ""} />
              {benchmarking ? "Benchmarking…" : "Run benchmark"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {benchmark?.results?.length ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {benchmark.results.map((item) => (
                <div key={item.workload} className="rounded-2xl border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{item.workload.replaceAll("_", " ")}</p>
                      <p className="mt-1 text-sm font-black">{item.worker.replaceAll("_", " ")}</p>
                    </div>
                    <Badge variant={item.promotion_candidate ? "default" : "secondary"}>
                      {item.promotion_candidate ? "Candidate" : "Keep shadow"}
                    </Badge>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-xl bg-muted/40 p-2"><span className="text-muted-foreground">Success</span><p className="font-black">{item.successes}/{item.iterations}</p></div>
                    <div className="rounded-xl bg-muted/40 p-2"><span className="text-muted-foreground">Parity</span><p className="font-black">{item.parity_passed}/{item.iterations}</p></div>
                    <div className="rounded-xl bg-muted/40 p-2"><span className="text-muted-foreground">Avg latency</span><p className="font-black">{item.avg_latency_ms == null ? "—" : `${item.avg_latency_ms} ms`}</p></div>
                    <div className="rounded-xl bg-muted/40 p-2"><span className="text-muted-foreground">Max latency</span><p className="font-black">{item.max_latency_ms == null ? "—" : `${item.max_latency_ms} ms`}</p></div>
                  </div>
                  <p className="mt-3 text-xs leading-5 text-muted-foreground">{item.recommendation.replaceAll("_", " ")}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground">
              No benchmark has been run in this browser session.
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Gauge className="h-5 w-5 text-primary" />Workload routing</CardTitle>
          <CardDescription>Promote specialized runtimes gradually instead of switching the whole platform at once.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {Object.entries(status?.routing ?? {}).map(([workload, route]) => (
            <div key={workload} className="rounded-2xl border p-4">
              <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{workload.replaceAll("_", " ")}</p>
              <div className="mt-3 flex items-center justify-between gap-3">
                <Badge variant={route.mode === "prefer-worker" ? "default" : "secondary"}>{route.mode}</Badge>
                <span className="text-[11px] text-muted-foreground">{route.env}</span>
              </div>
              <p className="mt-3 text-xs leading-5 text-muted-foreground">
                {route.mode === "off"
                  ? "Python only; worker is not called."
                  : route.mode === "shadow"
                    ? "Worker runs for comparison, but Python result remains authoritative."
                    : "Worker result may be accepted only after validation/parity checks."}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><CircuitBoard className="h-5 w-5 text-primary" />Authority and routing rules</CardTitle>
          <CardDescription>Worker acceleration never changes the final authority boundary.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Object.entries(status?.rules ?? {}).map(([key, value]) => (
            <div key={key} className="rounded-2xl border p-4">
              <p className="text-xs font-black uppercase tracking-wide text-muted-foreground">{key.replaceAll("_", " ")}</p>
              <p className="mt-2 font-black">{value.replaceAll("_", " ")}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="flex items-start gap-3 rounded-2xl border bg-muted/20 p-4 text-sm text-muted-foreground">
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
        <p>LoanHub can continue on Python when optional worker engines are disabled, unhealthy, too slow, or fail parity checks.</p>
      </div>
    </main>
  );
}
