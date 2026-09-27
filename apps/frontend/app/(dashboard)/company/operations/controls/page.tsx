"use client";

import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, RefreshCcw, Scale, ShoppingCart } from "lucide-react";

import { getPhase2Overview, getProcurementRequests, type Phase2Overview, type Phase2Record } from "@/api/companyOperationsPhase2";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function CompanyOperationsControlsPage() {
  const [overview, setOverview] = useState<Phase2Overview | null>(null);
  const [procurement, setProcurement] = useState<Phase2Record[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summary, requests] = await Promise.all([getPhase2Overview(), getProcurementRequests()]);
      setOverview(summary);
      setProcurement(requests);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load operational controls.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="space-y-6 pb-12">
      <section className="rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground"><ClipboardCheck className="h-4 w-4 text-primary" /> Operational Controls</div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Procurement, budgeting and internal audit</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">Native approval-controlled workflows for vendor procurement, fiscal planning and audit remediation.</p>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      {overview ? (
        <section className="grid gap-3 md:grid-cols-3">
          <Card><CardHeader><CardDescription className="flex items-center gap-2"><ShoppingCart className="h-4 w-4" /> Procurement</CardDescription><CardTitle>{overview.procurement.pending_approval}</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">requests awaiting management approval</CardContent></Card>
          <Card><CardHeader><CardDescription className="flex items-center gap-2"><Scale className="h-4 w-4" /> Budgeting</CardDescription><CardTitle>{overview.budgeting.approved_plans} approved</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">{overview.budgeting.draft_plans} draft budget plans</CardContent></Card>
          <Card><CardHeader><CardDescription className="flex items-center gap-2"><ClipboardCheck className="h-4 w-4" /> Internal audit</CardDescription><CardTitle>{overview.internal_audit.open_findings} findings</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">{overview.internal_audit.open_engagements} open engagements</CardContent></Card>
        </section>
      ) : null}

      <Card>
        <CardHeader><CardTitle>Procurement approval queue</CardTitle><CardDescription>Company/branch-scoped procurement requests with controlled submission and management approval.</CardDescription></CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-2xl border">
            <Table>
              <TableHeader><TableRow><TableHead>Reference</TableHead><TableHead>Title</TableHead><TableHead>Amount</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
              <TableBody>
                {procurement.slice(0, 20).map((row) => <TableRow key={row.id}><TableCell className="font-mono text-xs font-black text-primary">{row.reference ?? "—"}</TableCell><TableCell>{row.title ?? "—"}</TableCell><TableCell>{typeof row.amount === "number" ? `M ${row.amount.toLocaleString()}` : "—"}</TableCell><TableCell><Badge variant={row.status === "approved" ? "secondary" : "outline"}>{row.status ?? "unknown"}</Badge></TableCell></TableRow>)}
                {!procurement.length ? <TableRow><TableCell colSpan={4} className="h-24 text-center text-muted-foreground">No procurement requests yet.</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
