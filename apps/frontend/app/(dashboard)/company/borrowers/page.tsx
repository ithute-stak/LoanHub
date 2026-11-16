"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, BriefcaseBusiness, RefreshCcw, Search, UserRound } from "lucide-react";

import { listCompanyClients } from "@/api/companyClients";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoader } from "@/components/ui/page-loader";
import { formatMoney, titleCase } from "@/lib/format";
import type { CompanyClient } from "@/types/companyClient";

export default function BorrowerWorkspaceDirectoryPage() {
  const [clients, setClients] = useState<CompanyClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [directoryFilter, setDirectoryFilter] = useState<"all" | "active" | "overdue">("all");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setClients(await listCompanyClients({ limit: 1000 }));
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Borrower workspaces could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleClients = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = clients.filter((client) => directoryFilter === "all"
      || (directoryFilter === "active" && client.status === "active")
      || (directoryFilter === "overdue" && Number(client.overdue_installment_count || 0) > 0));
    if (!query) return filtered;
    return filtered.filter((client) => [
      client.full_name,
      client.account_reference,
      client.phone,
      client.email,
      client.national_id,
      client.passport_number,
      client.employer_name,
      client.district,
      client.town_or_village,
    ].some((value) => String(value ?? "").toLowerCase().includes(query)));
  }, [clients, directoryFilter, search]);

  const activeBorrowers = useMemo(() => clients.filter((client) => client.status === "active").length, [clients]);
  const overdueBorrowers = useMemo(() => clients.filter((client) => Number(client.overdue_installment_count || 0) > 0).length, [clients]);
  const totalOutstanding = useMemo(() => clients.reduce((sum, client) => sum + Number(client.outstanding_balance || 0), 0), [clients]);

  if (loading && clients.length === 0) return <PageLoader rows={8} />;

  return (
    <div className="loanhub-page space-y-5 pb-10">
      <section className="loanhub-hero flex flex-col gap-5 overflow-hidden rounded-3xl border border-primary/10 bg-gradient-to-br from-primary/[0.08] via-background to-background p-5 shadow-sm sm:p-7 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.22em] text-primary">One borrower · one operational history</p>
          <h1 className="mt-2 text-2xl font-black tracking-tight sm:text-3xl">Borrower directory</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Find a borrower and open their complete workspace for loans, repayments, documents, collections and activity history.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh
        </Button>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Borrowers" value={String(clients.length)} hint="Company client relationships" />
        <Metric label="Active" value={String(activeBorrowers)} hint="Active client accounts" />
        <Metric label="With overdue installments" value={String(overdueBorrowers)} hint="Needs recovery attention" />
        <Metric label="Outstanding exposure" value={formatMoney(totalOutstanding)} hint="Across this company portfolio" />
      </div>

      <Card className="loanhub-panel overflow-hidden rounded-2xl border shadow-sm">
        <CardHeader className="border-b bg-muted/20">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <CardTitle className="text-lg">Borrower workspaces</CardTitle>
              <CardDescription className="mt-1">Select a borrower to view their operational history.</CardDescription>
            </div>
            <div className="relative w-full lg:max-w-md">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" placeholder="Search borrower, account, phone, ID, employer or district…" />
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter borrowers">
              {([
                { value: "all", label: "All borrowers", count: clients.length },
                { value: "active", label: "Active", count: activeBorrowers },
                { value: "overdue", label: "Overdue", count: overdueBorrowers },
              ] as const).map((filter) => (
                <Button key={filter.value} size="sm" variant={directoryFilter === filter.value ? "default" : "outline"}
                  aria-pressed={directoryFilter === filter.value} onClick={() => setDirectoryFilter(filter.value)}>
                  {filter.label} <span className="ml-1 opacity-75">{filter.count}</span>
                </Button>
              ))}
            </div>
            <span className="text-xs font-medium text-muted-foreground" aria-live="polite">Showing {visibleClients.length} of {clients.length} borrowers</span>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5">
          {error ? (
            <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-5 text-sm text-destructive">{error}</div>
          ) : visibleClients.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed p-10 text-center">
              <UserRound className="h-8 w-8 text-muted-foreground/60" />
              <p className="text-sm text-muted-foreground">No borrowers match the current search and filters.</p>
              <Button size="sm" variant="outline" onClick={() => { setSearch(""); setDirectoryFilter("all"); }}>Clear filters</Button>
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {visibleClients.map((client) => (
                <Link
                  key={client.id}
                  href={`/company/borrowers/${client.borrower_id}`}
                  className="group rounded-2xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <UserRound className="h-5 w-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate font-black">{client.full_name}</span>
                        <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-primary" />
                      </span>
                      <span className="mt-1 block truncate text-xs text-muted-foreground">{client.account_reference} · {client.phone || "No phone"}</span>
                    </span>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    <Badge variant={client.status === "active" ? "default" : "secondary"}>{titleCase(client.status)}</Badge>
                    <Badge variant="outline">{client.loan_count} loan{client.loan_count === 1 ? "" : "s"}</Badge>
                    {client.overdue_installment_count > 0 ? <Badge variant="destructive">{client.overdue_installment_count} overdue</Badge> : null}
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-muted/30 p-3 text-xs">
                    <span><span className="block text-muted-foreground">Outstanding</span><span className="mt-1 block font-black">{formatMoney(client.outstanding_balance)}</span></span>
                    <span><span className="block text-muted-foreground">Employment</span><span className="mt-1 flex items-center gap-1 truncate font-bold"><BriefcaseBusiness className="h-3.5 w-3.5 text-primary" />{titleCase(client.employment_status || "unrecorded")}</span></span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="loanhub-stat">
      <p className="text-[10px] font-black uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-black">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}
