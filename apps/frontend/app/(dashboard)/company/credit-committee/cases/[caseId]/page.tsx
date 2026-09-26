"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Gavel,
  Loader2,
  RefreshCcw,
  Save,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

import {
  castCommitteeVote,
  downloadCreditMemo,
  finalizeCommitteeCase,
  getCommitteeCase,
  submitUnderwritingAssessment,
  updateCommitteeCondition,
  updateCommitteeGovernance,
  type CreditCommitteeCase,
} from "@/api/creditCommittee";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";

function errorText(error: unknown) {
  if (typeof error === "object" && error && "response" in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return error instanceof Error ? error.message : "The Credit Committee action failed.";
}

function lines(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function statusVariant(value: string) {
  if (["approved", "conditionally_approved", "satisfied"].includes(value)) return "secondary" as const;
  if (["rejected", "failed"].includes(value)) return "destructive" as const;
  return "outline" as const;
}

export default function CreditCommitteeCasePage() {
  const params = useParams<{ caseId: string }>();
  const [item, setItem] = useState<CreditCommitteeCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [assessment, setAssessment] = useState({
    proposed_amount: "", proposed_installment: "", proposed_term: "", verified_income: "", household_expenses: "", existing_debt_installments: "",
    risk_score: "", risk_grade: "medium", recommendation: "refer", rationale: "", strengths: "", weaknesses: "", exceptions: "", mitigants: "", conditions: "",
  });
  const [vote, setVote] = useState({ decision: "approve", rationale: "", conditions: "" });
  const [finalReason, setFinalReason] = useState("");
  const [overrideDecision, setOverrideDecision] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [governance, setGovernance] = useState({ required_votes: "2", threshold: "66.667", maker_checker: true, reason: "" });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await getCommitteeCase(params.caseId);
      setItem(next);
      setGovernance({ required_votes: String(next.required_votes), threshold: String(next.approval_threshold_percent), maker_checker: next.maker_checker_required, reason: "" });
      const memo = next.latest_assessment;
      if (memo) {
        setAssessment({
          proposed_amount: String(memo.proposed_amount), proposed_installment: String(memo.proposed_installment), proposed_term: String(memo.proposed_term), verified_income: String(memo.verified_income), household_expenses: String(memo.household_expenses), existing_debt_installments: String(memo.existing_debt_installments),
          risk_score: memo.risk_score == null ? "" : String(memo.risk_score), risk_grade: memo.risk_grade, recommendation: memo.recommendation, rationale: memo.rationale,
          strengths: memo.strengths.join("\n"), weaknesses: memo.weaknesses.join("\n"), exceptions: memo.exceptions.join("\n"), mitigants: memo.mitigants.join("\n"), conditions: memo.proposed_conditions.map((condition) => condition.title).join("\n"),
        });
      }
    } catch (nextError) {
      setError(errorText(nextError));
    } finally {
      setLoading(false);
    }
  }, [params.caseId]);

  useEffect(() => { void load(); }, [load]);

  const evidence = item?.evidence_snapshot ?? {};
  const affordability = (evidence.affordability ?? {}) as Record<string, any>;
  const bureau = (evidence.credit_bureau ?? {}) as Record<string, any>;
  const kyc = (evidence.kyc ?? {}) as Record<string, any>;
  const employment = (evidence.employment ?? {}) as Record<string, any>;
  const rules = (evidence.rules_engine ?? {}) as Record<string, any>;
  const openConditions = useMemo(() => item?.conditions.filter((condition) => !["satisfied", "waived"].includes(condition.status)) ?? [], [item]);

  async function run(label: string, action: () => Promise<unknown>, success: string) {
    setBusy(label); setError(null); setNotice(null);
    try { await action(); setNotice(success); await load(); }
    catch (nextError) { setError(errorText(nextError)); }
    finally { setBusy(null); }
  }

  async function saveAssessment() {
    await run("assessment", () => submitUnderwritingAssessment(params.caseId, {
      proposed_amount: assessment.proposed_amount ? Number(assessment.proposed_amount) : undefined,
      proposed_installment: assessment.proposed_installment ? Number(assessment.proposed_installment) : undefined,
      proposed_term: assessment.proposed_term ? Number(assessment.proposed_term) : undefined,
      verified_income: assessment.verified_income ? Number(assessment.verified_income) : undefined,
      household_expenses: assessment.household_expenses ? Number(assessment.household_expenses) : undefined,
      existing_debt_installments: assessment.existing_debt_installments ? Number(assessment.existing_debt_installments) : undefined,
      risk_score: assessment.risk_score ? Number(assessment.risk_score) : undefined,
      risk_grade: assessment.risk_grade as "low" | "medium" | "high" | "critical",
      recommendation: assessment.recommendation as "approve" | "approve_with_conditions" | "reject" | "refer",
      rationale: assessment.rationale,
      strengths: lines(assessment.strengths), weaknesses: lines(assessment.weaknesses), exceptions: lines(assessment.exceptions), mitigants: lines(assessment.mitigants),
      proposed_conditions: lines(assessment.conditions).map((title) => ({ title, condition_type: "pre_disbursement" as const })),
    }), "Underwriting credit memo submitted to committee.");
  }

  async function saveVote() {
    await run("vote", () => castCommitteeVote(params.caseId, {
      decision: vote.decision as "approve" | "approve_with_conditions" | "reject" | "abstain",
      rationale: vote.rationale,
      conditions: lines(vote.conditions).map((title) => ({ title, condition_type: "pre_disbursement" as const })),
    }), "Committee vote recorded with its rationale.");
  }

  async function finalize() {
    await run("finalize", () => finalizeCommitteeCase(params.caseId, {
      reason: finalReason || undefined,
      decision: overrideDecision ? overrideDecision as "approved" | "conditionally_approved" | "rejected" : undefined,
      override_reason: overrideReason || undefined,
    }), "Final committee decision recorded and locked.");
  }

  if (loading && !item) return <div className="flex min-h-[45vh] items-center justify-center"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="outline"><Link href="/company/credit-committee"><ArrowLeft className="mr-2 h-4 w-4" /> Credit Committee</Link></Button>
        <div className="flex gap-2"><Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCcw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</Button>{item ? <Button variant="outline" onClick={() => void downloadCreditMemo(item)}><Download className="mr-2 h-4 w-4" /> Credit memo PDF</Button> : null}</div>
      </div>

      {error ? <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm font-bold text-destructive">{error}</div> : null}
      {notice ? <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4 text-sm font-bold"><CheckCircle2 className="mr-2 inline h-4 w-4 text-emerald-600" />{notice}</div> : null}

      {item ? <>
        <section className="rounded-3xl border bg-card p-5 shadow-sm md:p-8">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between"><div><div className="flex flex-wrap items-center gap-2"><Badge variant={statusVariant(item.final_decision ?? item.status)}>{titleCase(item.final_decision ?? item.status)}</Badge><span className="font-mono text-xs font-black text-primary">{item.case_reference}</span></div><h1 className="mt-3 text-3xl font-black tracking-tight">{item.borrower_name}</h1><p className="mt-2 text-sm text-muted-foreground">Application {item.application_reference} · Requested {formatMoney(item.requested_amount)} · {item.term_count} term(s)</p></div><div className="rounded-2xl border bg-muted/20 p-4 text-sm"><p className="font-black">Committee control</p><p className="text-muted-foreground">{item.required_votes} decisive votes · {item.approval_threshold_percent}% approval threshold · maker-checker {item.maker_checker_required ? "on" : "off"}</p></div></div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Metric label="Verified income" value={formatMoney(Number(affordability.verified_income ?? 0))} />
          <Metric label="Household expenses" value={formatMoney(Number(affordability.household_expenses ?? 0))} />
          <Metric label="DTI" value={`${affordability.dti_percent ?? "—"}%`} />
          <Metric label="Credit score" value={String(bureau.score ?? "—")} />
          <Metric label="KYC" value={titleCase(String(kyc.status ?? "not available"))} />
          <Metric label="Rules engine" value={titleCase(String(rules.decision ?? "not run"))} />
        </section>

        <Card><CardHeader><CardTitle>Evidence pack</CardTitle><CardDescription>Captured evidence is frozen into each analyst memo so later source changes do not erase what the committee considered.</CardDescription></CardHeader><CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Evidence title="Affordability" rows={[['Decision', affordability.decision], ['Headroom', formatMoney(Number(affordability.affordability_headroom ?? 0))], ['Max installment', formatMoney(Number(affordability.maximum_affordable_installment ?? 0))]]} /><Evidence title="Credit bureau" rows={[['Score', bureau.score], ['Risk grade', bureau.risk_grade], ['Adverse records', bureau.adverse_records]]} /><Evidence title="KYC / risk" rows={[['Status', kyc.status], ['Sanctions hit', kyc.sanctions_hit ? 'Yes' : 'No'], ['Fraud flag', kyc.fraud_flag ? 'Yes' : 'No']]} /><Evidence title="Employment" rows={[['Status', employment.employment_status], ['Employer', employment.employer_name], ['Verification', employment.verification_status]]} /></CardContent></Card>

        {!item.locked_at ? <Card className="border-primary/30"><CardHeader><CardTitle>Analyst underwriting credit memo</CardTitle><CardDescription>A submitted revision is evidence, not an automatic approval. Once committee voting starts, the memo cannot be silently replaced.</CardDescription></CardHeader><CardContent className="space-y-4"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><Field label="Proposed amount"><Input type="number" value={assessment.proposed_amount} onChange={(event) => setAssessment((v) => ({ ...v, proposed_amount: event.target.value }))} /></Field><Field label="Proposed installment"><Input type="number" value={assessment.proposed_installment} onChange={(event) => setAssessment((v) => ({ ...v, proposed_installment: event.target.value }))} /></Field><Field label="Proposed term"><Input type="number" value={assessment.proposed_term} onChange={(event) => setAssessment((v) => ({ ...v, proposed_term: event.target.value }))} /></Field><Field label="Verified income"><Input type="number" value={assessment.verified_income} onChange={(event) => setAssessment((v) => ({ ...v, verified_income: event.target.value }))} /></Field><Field label="Household expenses"><Input type="number" value={assessment.household_expenses} onChange={(event) => setAssessment((v) => ({ ...v, household_expenses: event.target.value }))} /></Field><Field label="Existing debt installments"><Input type="number" value={assessment.existing_debt_installments} onChange={(event) => setAssessment((v) => ({ ...v, existing_debt_installments: event.target.value }))} /></Field><Field label="Risk score"><Input type="number" value={assessment.risk_score} onChange={(event) => setAssessment((v) => ({ ...v, risk_score: event.target.value }))} /></Field><Field label="Risk grade"><Select value={assessment.risk_grade} onValueChange={(value) => setAssessment((v) => ({ ...v, risk_grade: value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="low">Low</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="critical">Critical</SelectItem></SelectContent></Select></Field><Field label="Recommendation"><Select value={assessment.recommendation} onValueChange={(value) => setAssessment((v) => ({ ...v, recommendation: value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="approve">Approve</SelectItem><SelectItem value="approve_with_conditions">Approve with conditions</SelectItem><SelectItem value="refer">Refer</SelectItem><SelectItem value="reject">Reject</SelectItem></SelectContent></Select></Field></div><Field label="Rationale"><Textarea rows={5} value={assessment.rationale} onChange={(event) => setAssessment((v) => ({ ...v, rationale: event.target.value }))} /></Field><div className="grid gap-3 md:grid-cols-2"><Field label="Strengths — one per line"><Textarea rows={4} value={assessment.strengths} onChange={(event) => setAssessment((v) => ({ ...v, strengths: event.target.value }))} /></Field><Field label="Weaknesses — one per line"><Textarea rows={4} value={assessment.weaknesses} onChange={(event) => setAssessment((v) => ({ ...v, weaknesses: event.target.value }))} /></Field><Field label="Exceptions — one per line"><Textarea rows={4} value={assessment.exceptions} onChange={(event) => setAssessment((v) => ({ ...v, exceptions: event.target.value }))} /></Field><Field label="Mitigants — one per line"><Textarea rows={4} value={assessment.mitigants} onChange={(event) => setAssessment((v) => ({ ...v, mitigants: event.target.value }))} /></Field></div><Field label="Proposed pre-disbursement conditions — one per line"><Textarea rows={4} value={assessment.conditions} onChange={(event) => setAssessment((v) => ({ ...v, conditions: event.target.value }))} /></Field><div className="flex justify-end"><Button onClick={() => void saveAssessment()} disabled={busy !== null}><Save className="mr-2 h-4 w-4" /> Submit credit memo</Button></div></CardContent></Card> : null}

        <div className="grid gap-6 xl:grid-cols-2"><Card><CardHeader><CardTitle>Committee voting</CardTitle><CardDescription>The analyst cannot vote on the same case while maker-checker is enabled. Each member has one current vote; changes remain in the event trail.</CardDescription></CardHeader><CardContent className="space-y-4"><div className="grid gap-3 sm:grid-cols-2"><Field label="Vote"><Select value={vote.decision} onValueChange={(value) => setVote((v) => ({ ...v, decision: value }))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="approve">Approve</SelectItem><SelectItem value="approve_with_conditions">Approve with conditions</SelectItem><SelectItem value="reject">Reject</SelectItem><SelectItem value="abstain">Abstain</SelectItem></SelectContent></Select></Field><div className="rounded-xl border p-3 text-sm"><p className="font-black">Quorum</p><p className="text-muted-foreground">{item.vote_summary.decisive_vote_count}/{item.required_votes} decisive · {item.vote_summary.approval_ratio_percent}% approval-like</p></div></div><Field label="Vote rationale"><Textarea rows={4} value={vote.rationale} onChange={(event) => setVote((v) => ({ ...v, rationale: event.target.value }))} /></Field>{vote.decision === "approve_with_conditions" ? <Field label="Conditions — one per line"><Textarea rows={3} value={vote.conditions} onChange={(event) => setVote((v) => ({ ...v, conditions: event.target.value }))} /></Field> : null}<Button className="w-full" onClick={() => void saveVote()} disabled={busy !== null || item.status !== "committee_review"}><UserCheck className="mr-2 h-4 w-4" /> Record my committee vote</Button><div className="space-y-2">{item.votes.map((row) => <div key={row.id} className="rounded-xl border p-3"><div className="flex items-center justify-between gap-2"><p className="font-bold">{titleCase(row.role)}</p><Badge variant={statusVariant(row.decision === 'reject' ? 'rejected' : 'approved')}>{titleCase(row.decision)}</Badge></div><p className="mt-1 text-xs text-muted-foreground">{row.rationale}</p></div>)}</div></CardContent></Card>

        <Card><CardHeader><CardTitle>Committee governance & final decision</CardTitle><CardDescription>Default control is two decisive votes, a 66.667% threshold and maker-checker separation. The backend restricts overrides and control changes to authorised roles.</CardDescription></CardHeader><CardContent className="space-y-4"><div className="grid gap-3 sm:grid-cols-2"><Field label="Required decisive votes"><Input type="number" min={1} max={20} value={governance.required_votes} onChange={(event) => setGovernance((v) => ({ ...v, required_votes: event.target.value }))} /></Field><Field label="Approval threshold %"><Input type="number" min={1} max={100} step="0.001" value={governance.threshold} onChange={(event) => setGovernance((v) => ({ ...v, threshold: event.target.value }))} /></Field></div><label className="flex items-center gap-3 rounded-xl border p-3"><input type="checkbox" checked={governance.maker_checker} onChange={(event) => setGovernance((v) => ({ ...v, maker_checker: event.target.checked }))} /><span className="text-sm font-bold">Maker-checker separation required</span></label><Field label="Governance-change reason"><Input value={governance.reason} onChange={(event) => setGovernance((v) => ({ ...v, reason: event.target.value }))} /></Field><Button variant="outline" className="w-full" disabled={busy !== null || item.votes.length > 0 || Boolean(item.locked_at)} onClick={() => void run("governance", () => updateCommitteeGovernance(item.id, { required_votes: Number(governance.required_votes), approval_threshold_percent: Number(governance.threshold), maker_checker_required: governance.maker_checker, reason: governance.reason }), "Committee governance updated.")}><ShieldCheck className="mr-2 h-4 w-4" /> Save governance</Button><div className="rounded-2xl border bg-muted/20 p-4"><p className="font-black">Computed outcome</p><p className="text-sm text-muted-foreground">{item.vote_summary.computed_outcome ? titleCase(item.vote_summary.computed_outcome) : "Awaiting quorum"}</p></div>{!item.locked_at ? <><Field label="Final decision reason"><Textarea rows={3} value={finalReason} onChange={(event) => setFinalReason(event.target.value)} /></Field><Field label="Management override decision (optional)"><Select value={overrideDecision || "computed"} onValueChange={(value) => setOverrideDecision(value === "computed" ? "" : value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="computed">Use computed outcome</SelectItem><SelectItem value="approved">Approved</SelectItem><SelectItem value="conditionally_approved">Conditionally approved</SelectItem><SelectItem value="rejected">Rejected</SelectItem></SelectContent></Select></Field>{overrideDecision ? <Field label="Override reason"><Textarea rows={3} value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} /></Field> : null}<Button className="w-full" onClick={() => void finalize()} disabled={busy !== null || !item.vote_summary.quorum_met}><Gavel className="mr-2 h-4 w-4" /> Finalise committee decision</Button></> : <div className="rounded-xl border p-4 text-sm"><p className="font-black">Decision locked</p><p className="text-muted-foreground">{item.final_decision_reason}</p>{item.override_used ? <p className="mt-2 text-amber-700">Override: {item.override_reason}</p> : null}</div>}</CardContent></Card></div>

        <Card><CardHeader><CardTitle>Decision conditions</CardTitle><CardDescription>Pre-contract conditions block loan creation. Pre-disbursement conditions block payout. Satisfying a condition requires evidence; waivers require an authorised reason.</CardDescription></CardHeader><CardContent><div className="space-y-3">{item.conditions.map((condition) => <ConditionCard key={condition.id} item={item} condition={condition} busy={busy} run={run} />)}{!item.conditions.length ? <p className="text-sm text-muted-foreground">No committee conditions are recorded.</p> : null}</div>{openConditions.length ? <p className="mt-4 text-xs font-bold text-amber-700">{openConditions.length} condition(s) remain open or failed.</p> : null}</CardContent></Card>

        <Card><CardHeader><CardTitle>Audit timeline</CardTitle><CardDescription>Underwriting revisions, votes, governance changes, conditions and the final decision are retained in sequence.</CardDescription></CardHeader><CardContent className="space-y-3">{(item.events ?? []).map((event) => <div key={event.id} className="rounded-xl border p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-bold">{titleCase(event.event_type)}</p><span className="text-xs text-muted-foreground">{event.created_at ? formatDateTime(event.created_at) : "—"}</span></div><p className="mt-1 break-words font-mono text-[11px] text-muted-foreground">{JSON.stringify(event.payload)}</p></div>)}</CardContent></Card>
      </> : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) { return <Card><CardHeader className="pb-2"><CardDescription>{label}</CardDescription><CardTitle className="text-lg">{value}</CardTitle></CardHeader></Card>; }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="block space-y-1.5"><span className="text-xs font-black uppercase tracking-wide text-muted-foreground">{label}</span>{children}</label>; }
function Evidence({ title, rows }: { title: string; rows: Array<[string, unknown]> }) { return <div className="rounded-2xl border p-4"><p className="font-black">{title}</p><dl className="mt-3 space-y-2">{rows.map(([label, value]) => <div key={label} className="flex justify-between gap-3 text-xs"><dt className="text-muted-foreground">{label}</dt><dd className="text-right font-bold">{value == null || value === "" ? "—" : String(value)}</dd></div>)}</dl></div>; }

function ConditionCard({ item, condition, busy, run }: { item: CreditCommitteeCase; condition: CreditCommitteeCase["conditions"][number]; busy: string | null; run: (label: string, action: () => Promise<unknown>, success: string) => Promise<void> }) {
  const [evidence, setEvidence] = useState(condition.evidence_note ?? "");
  const [waiver, setWaiver] = useState(condition.waiver_reason ?? "");
  const locked = ["satisfied", "waived"].includes(condition.status);
  return <div className="rounded-2xl border p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-black">{condition.title}</p><p className="text-xs text-muted-foreground">{titleCase(condition.condition_type)}{condition.due_date ? ` · due ${condition.due_date}` : ""}</p></div><Badge variant={statusVariant(condition.status)}>{titleCase(condition.status)}</Badge></div>{condition.description ? <p className="mt-2 text-sm text-muted-foreground">{condition.description}</p> : null}{!locked ? <div className="mt-3 grid gap-3 md:grid-cols-2"><Field label="Satisfaction evidence"><Input value={evidence} onChange={(event) => setEvidence(event.target.value)} /></Field><Field label="Waiver reason"><Input value={waiver} onChange={(event) => setWaiver(event.target.value)} /></Field><div className="flex gap-2 md:col-span-2"><Button size="sm" disabled={busy !== null} onClick={() => void run(`condition:${condition.id}`, () => updateCommitteeCondition(item.id, condition.id, { status: "satisfied", evidence_note: evidence }), "Credit condition satisfied with evidence.")}><CheckCircle2 className="mr-2 h-4 w-4" /> Satisfy</Button><Button size="sm" variant="outline" disabled={busy !== null} onClick={() => void run(`condition:${condition.id}`, () => updateCommitteeCondition(item.id, condition.id, { status: "waived", waiver_reason: waiver }), "Credit condition formally waived.")}>Waive</Button><Button size="sm" variant="destructive" disabled={busy !== null} onClick={() => void run(`condition:${condition.id}`, () => updateCommitteeCondition(item.id, condition.id, { status: "failed", evidence_note: evidence }), "Credit condition marked failed.")}>Fail</Button></div></div> : <p className="mt-2 text-xs text-muted-foreground">{condition.evidence_note || condition.waiver_reason}</p>}</div>;
}
