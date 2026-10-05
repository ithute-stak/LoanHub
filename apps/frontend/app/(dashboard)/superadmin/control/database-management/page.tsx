"use client";

import {
  Activity,
  Database,
  HardDrive,
  Network,
  ShieldCheck,
  TableProperties,
  TimerReset,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";

type TableStat = {
  table_name: string;
  total_bytes: number;
  table_bytes: number;
  index_bytes: number;
  n_live_tup: number;
  n_dead_tup: number;
  seq_scan: number;
  idx_scan: number;
  n_tup_ins: number;
  n_tup_upd: number;
  n_tup_del: number;
  last_analyze: string | null;
  last_autoanalyze: string | null;
  last_autovacuum: string | null;
};

type IndexStat = {
  table_name: string;
  index_name: string;
  idx_scan: number;
  index_bytes: number;
};

type ConstraintStat = {
  constraint_name: string;
  table_name: string;
  definition: string;
};

type RowSecurityTable = {
  schema_name: string;
  table_name: string;
  rls_enabled: boolean;
  force_rls: boolean;
  table_owner: string;
  policy_count: number;
};

type DatabaseHealth = {
  supported: boolean;
  database_engine: string;
  database_name?: string;
  database_size_bytes?: number;
  connections?: {
    max: number;
    active: number;
    idle: number;
    idle_in_transaction: number;
  };
  transactions?: {
    commits: number;
    rollbacks: number;
    deadlocks: number;
    long_running_over_60s: number;
    oldest_seconds: number;
    blocked_sessions: number;
  };
  io?: {
    blocks_read: number;
    blocks_hit: number;
    cache_hit_percent: number;
    temp_files: number;
    temp_bytes: number;
  };
  tuple_activity?: {
    returned: number;
    fetched: number;
    inserted: number;
    updated: number;
    deleted: number;
  };
  replication?: {
    is_replica: boolean;
    connected_replicas: number;
  };
  row_security?: {
    runtime_role: string;
    runtime_is_superuser: boolean;
    runtime_bypass_rls: boolean;
    runtime_owns_rls_table: boolean;
    enabled_table_count: number;
    enforcement_ready: boolean;
    tables: RowSecurityTable[];
  };
  alembic_heads?: string[];
  unvalidated_check_constraints?: ConstraintStat[];
  largest_tables?: TableStat[];
  largest_indexes?: IndexStat[];
  message?: string;
};

function bytes(value = 0) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size >= 100 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function number(value = 0) {
  return Number(value || 0).toLocaleString();
}

export default function DatabaseManagementPage() {
  const [health, setHealth] = useState<DatabaseHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await api.get<DatabaseHealth>("/platform-owner/database/health");
      setHealth(response.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Database health could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const warnings = useMemo(() => {
    if (!health?.supported) return [];
    const items: string[] = [];
    if ((health.transactions?.blocked_sessions ?? 0) > 0) items.push("Blocked PostgreSQL sessions detected.");
    if ((health.transactions?.long_running_over_60s ?? 0) > 0) items.push("Long-running transactions over 60 seconds detected.");
    if ((health.transactions?.deadlocks ?? 0) > 0) items.push("PostgreSQL has recorded deadlocks since statistics were reset.");
    if ((health.connections?.idle_in_transaction ?? 0) > 0) items.push("Idle-in-transaction sessions are holding database resources.");
    if ((health.io?.cache_hit_percent ?? 100) < 95) items.push("Database cache-hit ratio is below 95%.");
    if ((health.unvalidated_check_constraints?.length ?? 0) > 0) items.push("Integrity constraints are awaiting historical-data validation.");
    return items;
  }, [health]);

  if (loading) {
    return <main className="p-6"><div className="rounded-3xl border bg-card p-8">Loading database telemetry…</div></main>;
  }

  return (
    <main className="space-y-6">
      <section className="rounded-3xl border bg-card p-6 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Database className="h-6 w-6" /></div>
            <p className="mt-5 text-xs font-black uppercase tracking-[0.2em] text-primary">System Owner · Database Management</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight md:text-4xl">PostgreSQL operating health</h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground md:text-base">Read-only workload, transaction, index, table-size and integrity telemetry for safe database tuning.</p>
          </div>
          <button onClick={() => void load()} className="inline-flex h-11 items-center justify-center rounded-xl border px-4 text-sm font-black hover:border-primary hover:text-primary">Refresh telemetry</button>
        </div>
      </section>

      {error ? <section className="rounded-3xl border border-red-500/30 bg-red-500/10 p-5 text-sm font-bold text-red-700">{error}</section> : null}
      {health && !health.supported ? <section className="rounded-3xl border bg-card p-6">{health.message}</section> : null}

      {health?.supported ? (
        <>
          {warnings.length ? (
            <section className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-5">
              <div className="flex gap-3">
                <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
                <div><p className="font-black text-amber-800">Database attention</p><div className="mt-2 space-y-1 text-sm text-amber-800/80">{warnings.map((item) => <p key={item}>• {item}</p>)}</div></div>
              </div>
            </section>
          ) : (
            <section className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 p-5"><div className="flex items-center gap-3"><ShieldCheck className="h-5 w-5 text-emerald-700" /><p className="font-black text-emerald-800">No immediate database-health warnings detected.</p></div></section>
          )}

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-3xl border bg-card p-5"><HardDrive className="h-5 w-5 text-primary" /><p className="mt-3 text-2xl font-black">{bytes(health.database_size_bytes)}</p><p className="text-xs font-bold text-muted-foreground">{health.database_name} database size</p></div>
            <div className="rounded-3xl border bg-card p-5"><Network className="h-5 w-5 text-primary" /><p className="mt-3 text-2xl font-black">{number(health.connections?.active)} / {number(health.connections?.max)}</p><p className="text-xs font-bold text-muted-foreground">Active / maximum connections</p></div>
            <div className="rounded-3xl border bg-card p-5"><Activity className="h-5 w-5 text-primary" /><p className="mt-3 text-2xl font-black">{health.io?.cache_hit_percent?.toFixed(2)}%</p><p className="text-xs font-bold text-muted-foreground">Buffer cache hit ratio</p></div>
            <div className="rounded-3xl border bg-card p-5"><TimerReset className="h-5 w-5 text-primary" /><p className="mt-3 text-2xl font-black">{number(health.transactions?.long_running_over_60s)}</p><p className="text-xs font-bold text-muted-foreground">Transactions running over 60s</p></div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-3xl border bg-card p-6 shadow-sm">
              <h2 className="text-xl font-black">Transaction & concurrency health</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {[
                  ["Commits", number(health.transactions?.commits)],
                  ["Rollbacks", number(health.transactions?.rollbacks)],
                  ["Deadlocks", number(health.transactions?.deadlocks)],
                  ["Blocked sessions", number(health.transactions?.blocked_sessions)],
                  ["Idle in transaction", number(health.connections?.idle_in_transaction)],
                  ["Oldest transaction", `${Math.round(health.transactions?.oldest_seconds ?? 0)}s`],
                  ["Temporary files", number(health.io?.temp_files)],
                  ["Temporary bytes", bytes(health.io?.temp_bytes)],
                ].map(([label, value]) => <div key={label} className="rounded-2xl border bg-muted/20 p-4"><p className="text-xs font-bold text-muted-foreground">{label}</p><p className="mt-1 text-lg font-black">{value}</p></div>)}
              </div>
            </div>

            <div className="rounded-3xl border bg-card p-6 shadow-sm">
              <h2 className="text-xl font-black">Recovery & schema state</h2>
              <div className="mt-4 space-y-3">
                <div className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">Role</p><p className="mt-1 font-black">{health.replication?.is_replica ? "Replica / recovery" : "Primary"}</p></div>
                <div className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">Connected replicas</p><p className="mt-1 font-black">{number(health.replication?.connected_replicas)}</p></div>
                <div className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">Alembic head</p><p className="mt-1 break-all font-mono text-sm font-bold">{health.alembic_heads?.join(", ") || "Unknown"}</p></div>
                <div className="rounded-2xl border p-4"><p className="text-xs font-bold text-muted-foreground">Unvalidated CHECK constraints</p><p className="mt-1 font-black">{number(health.unvalidated_check_constraints?.length)}</p></div>
              </div>
            </div>
          </section>

          <section className="rounded-3xl border bg-card p-6 shadow-sm">
            <div className="flex items-center gap-3"><TableProperties className="h-5 w-5 text-primary" /><h2 className="text-xl font-black">Largest / busiest user tables</h2></div>
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="border-b text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="py-3 pr-4">Table</th><th className="pr-4">Total</th><th className="pr-4">Rows</th><th className="pr-4">Dead rows</th><th className="pr-4">Seq scans</th><th className="pr-4">Index scans</th><th>Index size</th></tr></thead>
                <tbody>{health.largest_tables?.map((row) => <tr key={row.table_name} className="border-b last:border-0"><td className="py-3 pr-4 font-bold">{row.table_name}</td><td className="pr-4">{bytes(row.total_bytes)}</td><td className="pr-4">{number(row.n_live_tup)}</td><td className="pr-4">{number(row.n_dead_tup)}</td><td className="pr-4">{number(row.seq_scan)}</td><td className="pr-4">{number(row.idx_scan)}</td><td>{bytes(row.index_bytes)}</td></tr>)}</tbody>
              </table>
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-3xl border bg-card p-6 shadow-sm">
              <h2 className="text-xl font-black">Largest indexes</h2>
              <div className="mt-4 space-y-2">{health.largest_indexes?.slice(0, 15).map((row) => <div key={row.index_name} className="rounded-2xl border p-4"><div className="flex items-start justify-between gap-4"><div><p className="break-all text-sm font-black">{row.index_name}</p><p className="mt-1 text-xs text-muted-foreground">{row.table_name} · {number(row.idx_scan)} scans</p></div><span className="shrink-0 text-sm font-bold">{bytes(row.index_bytes)}</span></div></div>)}</div>
            </div>
            <div className="rounded-3xl border bg-card p-6 shadow-sm">
              <h2 className="text-xl font-black">Integrity validation queue</h2>
              <p className="mt-1 text-sm text-muted-foreground">New writes already obey these CHECK constraints; historical rows should be audited before validation.</p>
              <div className="mt-4 space-y-2">{health.unvalidated_check_constraints?.length ? health.unvalidated_check_constraints.map((row) => <div key={row.constraint_name} className="rounded-2xl border p-4"><p className="text-sm font-black">{row.constraint_name}</p><p className="mt-1 text-xs text-muted-foreground">{row.table_name}</p><p className="mt-2 break-words font-mono text-xs">{row.definition}</p></div>) : <p className="rounded-2xl border p-4 text-sm text-muted-foreground">No pending CHECK-constraint validations.</p>}</div>
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
