"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BriefcaseBusiness, Gavel, MessageSquareWarning, RefreshCcw, ShieldCheck, UsersRound } from "lucide-react";

import {
  getCollateralAssets,
  getCompanyOperationsOverview,
  getComplaintCases,
  getCrmCases,
  getLegalRecoveryMatters,
  type CompanyOperationRecord,
  type CompanyOperationsOverview,
} from "@/api/companyOperations";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { titleCase } from "@/lib/format";

function text(value: unknown, fallback = "—") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function statusBadge(value: unknown) {
  const status = text(value, "unknown");
  return <Badge variant={status === "resolved" || status === "released" || status === "closed" ? "secondary" : status === "escalated" ? "destructive" : "outline"}>{titleCase(status)}</Badge>;
}

function OperationsTable({ rows, columns }: { rows: CompanyOperationRecord[]; columns: Array<{ key: string; label: string }> }) {
  return (
    <div className="overflow-x-auto rounded-2xl border">
      <Table>
        <TableHeader><TableRow><TableHead>Reference</TableHead>{columns.map((column) => <TableHead key={column.key}>{column.label}</TableHead>)}<TableHead>Status</TableHead></TableRow></TableHeader>
        <TableBody>
          {rows.slice(0, 15).map((row) => (
            <TableRow key={row.id}>
              <TableCell className="font-mono text-xs font-black text-primary">{row.reference}</TableCell>
              {columns.map((column) => <TableCell key={column.key}>{text(row[column.key])}</TableCell>)}
              <TableCell>{statusBadge(row.status)}</TableCell>
            </TableRow>
          ))}
          {!rows.length ? <TableRow><TableCell colSpan={columns.length + 2} className="h-24 text-center text-muted-foreground">No records yet.</TableCell></TableRow> : null}
        </TableBody>
      </Table>
    </div>
  );
}

export default function CompanyOperationsPage() {
  const [overview, setOverview] = useState<CompanyOperationsOverview | null>(null);
  const [crm, setCrm] = useState<CompanyOperationRecord[]>([]);
  const [collateral, setCollateral] = useState<CompanyOperationRecord[]>([]);
  const [legal, setLegal] = useState<CompanyOperationRecord[]>([]);
  const [complaints, setComplaints] = useState<CompanyOperationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summary, crmRows, collateralRows, legalRows, complaintRows] = await Promise.all([
        getCompanyOperationsOverview(), getCrmCases(), getCollateralAssets(), getLegalRecoveryMatters(), getComplaintCases(),
      ]);
      setOverview(summary); setCrm(crmRows); setCollateral(collateralRows); setLegal(legalRows); setComplaints(complaintRows);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load company operations.");
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
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black text-muted-foreground"><BriefcaseBusiness className="h-4 w-4 text-primary" /> Specialised Company Operations</div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Native operational workflows, not generic records</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">CRM follow-ups, collateral controls, legal-recovery matters and complaints now have dedicated company/branch-scoped data models, operational statuses, deadlines and audit events.</p>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      {overview ? (
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Card><CardHeader><CardDescription className="flex items-center gap-2"><UsersRound className="h-4 w-4" /> CRM</CardDescription><CardTitle>{overview.crm.open} open</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground"><p>{overview.crm.followups_due} follow-ups due</p><p>{overview.crm.retention_risk} high/critical retention risks</p></CardContent></Card>
          <Card><CardHeader><CardDescription className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Collateral</CardDescription><CardTitle>{overview.collateral.held} held</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground"><p>{overview.collateral.unperfected} unperfected</p><p>{overview.collateral.release_requested} release requests</p></CardContent></Card>
          <Card><CardHeader><CardDescription className="flex items-center gap-2"><Gavel className="h-4 w-4" /> Legal recovery</CardDescription><CardTitle>{overview.legal.open} open</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground"><p>{overview.legal.court_dates_due} court dates in 14 days</p><p>{overview.legal.limitation_attention} limitation deadlines in 30 days</p></CardContent></Card>
          <Card className={overview.complaints.sla_breached ? "border-amber-500/40" : undefined}><CardHeader><CardDescription className="flex items-center gap-2"><MessageSquareWarning className="h-4 w-4" /> Complaints</CardDescription><CardTitle>{overview.complaints.open} open</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground"><p>{overview.complaints.sla_breached} SLA breaches</p><p>{overview.complaints.regulatory_reportable} regulatory-reportable</p></CardContent></Card>
        </section>
      ) : null}

      {overview?.complaints.sla_breached ? <div className="flex items-center gap-2 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm font-bold"><AlertTriangle className="h-4 w-4 text-amber-600" /> Complaint SLA breaches require operational attention.</div> : null}

      <Card><CardHeader><CardTitle>CRM relationship cases</CardTitle><CardDescription>Borrower relationship stage, segmentation, next action and retention-risk queue.</CardDescription></CardHeader><CardContent><OperationsTable rows={crm} columns={[{ key: "relationship_stage", label: "Stage" }, { key: "segment", label: "Segment" }, { key: "retention_risk", label: "Retention risk" }, { key: "next_action_at", label: "Next action" }]} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Collateral register</CardTitle><CardDescription>Ownership, valuation, perfection, insurance and controlled release status.</CardDescription></CardHeader><CardContent><OperationsTable rows={collateral} columns={[{ key: "asset_type", label: "Asset" }, { key: "ownership_name", label: "Owner" }, { key: "valuation_amount", label: "Valuation" }, { key: "perfected", label: "Perfected" }]} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Legal recovery matters</CardTitle><CardDescription>Counsel, court details, legal stage, claim amount and deadline intelligence.</CardDescription></CardHeader><CardContent><OperationsTable rows={legal} columns={[{ key: "legal_stage", label: "Stage" }, { key: "counsel_name", label: "Counsel" }, { key: "court_case_number", label: "Court case" }, { key: "next_court_at", label: "Next court" }]} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Complaint cases</CardTitle><CardDescription>SLA-controlled complaint handling with escalation, root-cause and regulatory-reportability evidence.</CardDescription></CardHeader><CardContent><OperationsTable rows={complaints} columns={[{ key: "category", label: "Category" }, { key: "severity", label: "Severity" }, { key: "sla_due_at", label: "SLA due" }, { key: "regulatory_reportable", label: "Regulatory" }]} /></CardContent></Card>
    </div>
  );
}
