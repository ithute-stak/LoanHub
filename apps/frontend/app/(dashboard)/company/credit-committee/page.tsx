"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  Gavel,
  Loader2,
  RefreshCcw,
  Scale,
  ShieldAlert,
  UsersRound,
} from "lucide-react";

import {
  getCommitteeDashboard,
  intakeCommitteeApplication,
  type CommitteeDashboard,
  type CreditCommitteeCase,
} from "@/api/creditCommittee";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "Credit Committee data could not be loaded.";
}

function tone(status: string) {
  if (["approved"].includes(status)) return "secondary" as const;
  if (["rejected", "cancelled"].includes(status)) return "destructive" as const;
  return "outline" as const;
}

export default function CreditCommitteePage() {
  const [dashboard, setDashboard] = useState<CommitteeDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDashboard(await getCommitteeDashboard());
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function intake(applicationId: string) {
    setBusy(applicationId);
    setError(null);
    try {
      const item = await intakeCommitteeApplication(applicationId);
      window.location.assign(`/company/credit-committee/cases/${item.id}`);
    } catch (nextError) {
      setError(errorText(nextError));
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6 pb-12">
      <section className="overflow-hidden rounded-3xl border bg-card p-5 shadow-sm md:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1.5 text-xs font-black uppercase tracking-[0.16em] text-primary">
              <Gavel className="h-4 w-4" /> Credit Committee & Underwriting
            </div>
            <h1 className="mt-4 text-3xl font-black tracking-tight md:text-4xl">Human credit judgement with evidence and controls</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground md:text-base">
              Move applications from analyst assessment through independent committee voting, documented conditions and final decision. Automated scores remain evidence; they do not silently become the human approval.
            </p>
          </div>
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            <RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}

      {dashboard ? (
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Metric icon={FileSearch} label="Awaiting intake" value={dashboard.summary.awaiting_intake} />
          <Metric icon={ClipboardCheck} label="Underwriting" value={dashboard.summary.underwriting} />
          <Metric icon={UsersRound} label="Committee review" value={dashboard.summary.committee_review} />
          <Metric icon={ShieldAlert} label="Awaiting conditions" value={dashboard.summary.awaiting_conditions} />
          <Metric icon={CheckCircle2} label="Approved" value={dashboard.summary.approved} />
          <Metric icon={Scale} label="Rejected" value={dashboard.summary.rejected} />
        </section>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Applications awaiting Credit Committee intake</CardTitle>
          <CardDescription>New governed applications cannot be converted into loans until this workflow records a positive final committee decision.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-2xl border">
            <Table>
              <TableHeader><TableRow><TableHead>Application</TableHead><TableHead>Borrower</TableHead><TableHead>Requested</TableHead><TableHead>Term</TableHead><TableHead>Submitted</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader>
              <TableBody>
                {(dashboard?.awaiting_intake ?? []).map((item) => (
                  <TableRow key={item.application_id}>
                    <TableCell><p className="font-mono text-xs font-black text-primary">{item.application_reference}</p><Badge className="mt-1" variant="outline">{titleCase(item.status)}</Badge></TableCell>
                    <TableCell className="font-bold">{item.borrower_name}</TableCell>
                    <TableCell className="font-bold">{formatMoney(item.requested_amount)}</TableCell>
                    <TableCell>{item.term_count}</TableCell>
                    <TableCell>{item.submitted_at ? formatDateTime(item.submitted_at) : "—"}</TableCell>
                    <TableCell className="text-right"><Button size="sm" onClick={() => void intake(item.application_id)} disabled={busy === item.application_id}>{busy === item.application_id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ClipboardCheck className="mr-2 h-4 w-4" />} Open underwriting</Button></TableCell>
                  </TableRow>
                ))}
                {!loading && !dashboard?.awaiting_intake.length ? <TableRow><TableCell colSpan={6} className="h-24 text-center text-muted-foreground">No governed applications are waiting for intake.</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Credit Committee case register</CardTitle>
          <CardDescription>Every analyst memo, vote, condition, override and final decision remains attached to its case reference.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-2xl border">
            <Table>
              <TableHeader><TableRow><TableHead>Case</TableHead><TableHead>Borrower</TableHead><TableHead>Requested</TableHead><TableHead>Analyst</TableHead><TableHead>Committee</TableHead><TableHead>Conditions</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Open</TableHead></TableRow></TableHeader>
              <TableBody>
                {(dashboard?.cases ?? []).map((item) => <CaseRow key={item.id} item={item} />)}
                {!loading && !dashboard?.cases.length ? <TableRow><TableCell colSpan={8} className="h-24 text-center text-muted-foreground">No Credit Committee cases have been opened yet.</TableCell></TableRow> : null}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Gavel; label: string; value: number }) {
  return <Card><CardHeader className="pb-2"><CardDescription className="flex items-center gap-2"><Icon className="h-4 w-4 text-primary" />{label}</CardDescription><CardTitle>{value}</CardTitle></CardHeader></Card>;
}

function CaseRow({ item }: { item: CreditCommitteeCase }) {
  const openConditions = item.conditions.filter((condition) => !["satisfied", "waived"].includes(condition.status)).length;
  return (
    <TableRow>
      <TableCell><p className="font-mono text-xs font-black text-primary">{item.case_reference}</p><p className="mt-1 text-[11px] text-muted-foreground">{item.application_reference}</p></TableCell>
      <TableCell className="font-bold">{item.borrower_name}</TableCell>
      <TableCell>{formatMoney(item.requested_amount)}</TableCell>
      <TableCell>{item.latest_assessment ? <><Badge variant="outline">{titleCase(item.latest_assessment.recommendation)}</Badge><p className="mt-1 text-xs text-muted-foreground">Risk {titleCase(item.latest_assessment.risk_grade)}</p></> : <span className="text-xs text-muted-foreground">Awaiting memo</span>}</TableCell>
      <TableCell><p className="font-bold">{item.vote_summary.decisive_vote_count}/{item.required_votes} votes</p><p className="text-xs text-muted-foreground">{item.vote_summary.approval_ratio_percent}% approval-like</p></TableCell>
      <TableCell>{openConditions ? <Badge variant="destructive">{openConditions} open</Badge> : <Badge variant="secondary">Clear</Badge>}</TableCell>
      <TableCell><Badge variant={tone(item.status)}>{titleCase(item.final_decision ?? item.status)}</Badge></TableCell>
      <TableCell className="text-right"><Button asChild size="sm" variant="outline"><Link href={`/company/credit-committee/cases/${item.id}`}>Open case</Link></Button></TableCell>
    </TableRow>
  );
}
