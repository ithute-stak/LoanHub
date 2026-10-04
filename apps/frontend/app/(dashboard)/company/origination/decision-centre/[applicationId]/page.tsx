"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeCheck,
  Building2,
  Calculator,
  CheckCircle2,
  CircleAlert,
  FileSearch,
  Gauge,
  RefreshCcw,
  ShieldCheck,
  UserCheck,
  WalletCards,
} from "lucide-react";

import { originationApi } from "@/api/origination";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/page-loader";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import type { OriginationWorkspace } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

function StateRow({ label, value, ok }: { label: string; value: string; ok?: boolean | null }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-2xl border bg-muted/10 p-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`text-right text-sm font-black ${ok === false ? "text-destructive" : ok === true ? "text-emerald-700" : ""}`}>{value}</span>
    </div>
  );
}

function TimelineRow({ title, detail, date }: { title: string; detail: string; date?: string | null }) {
  return (
    <div className="relative border-l pl-5">
      <span className="absolute -left-1.5 top-1 h-3 w-3 rounded-full border bg-background" />
      <p className="font-black">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
      {date ? <p className="mt-1 text-[11px] text-muted-foreground">{formatDate(date)}</p> : null}
    </div>
  );
}

export default function LoanDecisionCentrePage() {
  const params = useParams<{ applicationId: string }>();
  const applicationId = params.applicationId;
  const [workspace, setWorkspace] = useState<OriginationWorkspace | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setWorkspace(await originationApi.getWorkspace(applicationId));
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The loan decision centre could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    void load();
  }, [load]);

  const assessment = workspace?.assessments[0] ?? workspace?.application.affordability_assessment ?? null;
  const readiness = workspace?.integration_readiness;

  const decision = readiness?.final_decision ?? "action_required";
  const decisionLabel = decision === "loanable"
    ? "LOANABLE"
    : decision === "not_loanable"
      ? "NOT LOANABLE"
      : "ACTION REQUIRED";

  const decisionTone = decision === "loanable"
    ? "border-emerald-500/30 bg-emerald-500/5"
    : decision === "not_loanable"
      ? "border-destructive/30 bg-destructive/5"
      : "border-amber-500/30 bg-amber-500/5";

  const timeline = useMemo(() => {
    if (!workspace) return [];
    const items: Array<{ title: string; detail: string; date?: string | null }> = [];
    items.push({
      title: "Application created",
      detail: `${workspace.application.application_reference} · ${workspace.application.borrower_name}`,
      date: workspace.application.created_at,
    });
    if (assessment) {
      items.push({
        title: "Affordability assessed",
        detail: `${titleCase(assessment.overridden ? assessment.override_decision ?? assessment.decision : assessment.decision)} · policy version ${assessment.policy_version}`,
        date: assessment.created_at,
      });
    }
    if (readiness?.bureau.fresh) {
      items.push({
        title: "Experian evidence available",
        detail: `Score ${readiness.bureau.score ?? "—"} · ${readiness.bureau.risk_band ?? "no risk band"}`,
        date: readiness.bureau.completed_at,
      });
    }
    if (readiness?.cdas.verified) {
      items.push({
        title: "CDAS payroll identity verified",
        detail: `Employee ${readiness.cdas.employee_number ?? "—"}${readiness.cdas.department ? ` · ${readiness.cdas.department}` : ""}`,
        date: readiness.cdas.verified_at,
      });
    }
    if (workspace.application.submitted_at) {
      items.push({
        title: "Submitted for lending decision",
        detail: "Application entered the manager decision workflow.",
        date: workspace.application.submitted_at,
      });
    }
    if (workspace.application.approved_at) {
      items.push({
        title: "Loan approved",
        detail: workspace.application.loan_reference ? `Loan ${workspace.application.loan_reference}` : "Loan approved",
        date: workspace.application.approved_at,
      });
    }
    return items;
  }, [assessment, readiness, workspace]);

  if (loading) return <PageLoader rows={10} />;
  if (!workspace || !readiness) {
    return (
      <main className="loanhub-page">
        <Alert variant="destructive">
          <CircleAlert className="h-4 w-4" />
          <AlertTitle>Decision data unavailable</AlertTitle>
          <AlertDescription>This application could not be loaded.</AlertDescription>
        </Alert>
      </main>
    );
  }

  const application = workspace.application;

  return (
    <main className="loanhub-page space-y-5">
      <section className={`rounded-3xl border p-6 shadow-sm sm:p-8 ${decisionTone}`}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Unified Loan Decision Centre</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight">{application.borrower_name}</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {application.application_reference} · {application.product_name ?? "Loan product not selected"} · {formatMoney(application.requested_amount)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh evidence</Button>
            <Button variant="outline" asChild><Link href={`/company/origination/new?application=${application.id}`}><Calculator className="h-4 w-4" />Edit / recalculate</Link></Button>
            <Button asChild><Link href={`/company/marketplace?workspace=applications&application=${application.id}`}><FileSearch className="h-4 w-4" />Manager decision</Link></Button>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 rounded-3xl border bg-background/80 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-muted-foreground">Final decision</p>
            <p className={`mt-1 text-3xl font-black ${decision === "loanable" ? "text-emerald-700" : decision === "not_loanable" ? "text-destructive" : "text-amber-700"}`}>{decisionLabel}</p>
          </div>
          <Badge variant={readiness.ready_for_approval ? "default" : "secondary"}>
            {readiness.ready_for_approval ? "Ready for approval" : `${readiness.blockers.length} blocker(s)`}
          </Badge>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5 text-primary" />Core LoanHub</CardTitle>
            <CardDescription>Internal borrower, KYC and affordability decision.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <StateRow label="Application status" value={titleCase(readiness.core.status)} />
            <StateRow label="KYC" value={titleCase(readiness.core.kyc_status ?? "not available")} ok={readiness.core.kyc_status === "verified"} />
            <StateRow label="Affordability" value={titleCase(readiness.core.affordability_decision ?? "not assessed")} ok={readiness.core.ready_for_approval} />
            {assessment ? (
              <>
                <StateRow label="Verified income" value={formatMoney(assessment.verified_income)} />
                <StateRow label="Current debt installments" value={formatMoney(assessment.existing_debt_installments)} />
                <StateRow label="Proposed installment" value={formatMoney(assessment.proposed_installment)} />
                <StateRow label="Affordable limit" value={formatMoney(assessment.maximum_affordable_installment)} ok={Number(assessment.affordability_headroom) >= 0} />
                <StateRow label="Headroom" value={formatMoney(assessment.affordability_headroom)} ok={Number(assessment.affordability_headroom) >= 0} />
                <StateRow label="DTI" value={`${Number(assessment.dti_percent).toFixed(1)}%`} />
              </>
            ) : null}
          </CardContent>
        </Card>

        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" />Experian / Bureau</CardTitle>
            <CardDescription>Credit-bureau policy and evidence used by Core LoanHub.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <StateRow label="Enabled" value={readiness.bureau.enabled ? "Yes" : "No / optional"} ok={!readiness.bureau.enabled || readiness.bureau.platform_ready} />
            {readiness.bureau.enabled ? (
              <>
                <StateRow label="Environment" value={titleCase(readiness.bureau.environment)} />
                <StateRow label="Platform connection" value={readiness.bureau.platform_ready ? "Ready" : "Not ready"} ok={readiness.bureau.platform_ready} />
                <StateRow label="Fresh report" value={readiness.bureau.fresh ? "Yes" : "No"} ok={!readiness.bureau.required_before_approval || readiness.bureau.fresh} />
                <StateRow label="Score" value={readiness.bureau.score == null ? "—" : String(readiness.bureau.score)} />
                <StateRow label="Risk band" value={readiness.bureau.risk_band ?? "—"} />
                <StateRow label="Defaults" value={readiness.bureau.defaults_count == null ? "—" : String(readiness.bureau.defaults_count)} ok={readiness.bureau.defaults_count === 0} />
                <StateRow label="Identity match" value={readiness.bureau.identity_match == null ? "—" : readiness.bureau.identity_match ? "Match" : "Not matched"} ok={readiness.bureau.identity_match} />
                <StateRow label="Monthly commitments" value={formatMoney(readiness.bureau.monthly_commitments ?? 0)} />
                <StateRow label="Used in affordability" value={readiness.bureau.used_in_affordability ? "Yes" : "No"} />
              </>
            ) : null}
            <Button variant="outline" className="w-full" asChild>
              <Link href={`/company/origination/experian?application=${application.id}`}>Open Experian evidence</Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><UserCheck className="h-5 w-5 text-primary" />CDAS</CardTitle>
            <CardDescription>Payroll identity, provider readiness and collection choice.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <StateRow label="Payroll collection selected" value={readiness.cdas.selected_for_collection ? "Yes" : "No"} />
            {readiness.cdas.selected_for_collection ? (
              <>
                <StateRow label="Environment" value={titleCase(readiness.cdas.provider_environment ?? "test")} />
                <StateRow label="Company connection" value={readiness.cdas.provider_configured && readiness.cdas.provider_enabled ? "Ready" : "Not ready"} ok={readiness.cdas.provider_configured && readiness.cdas.provider_enabled} />
                <StateRow label="Connection tested" value={readiness.cdas.provider_tested ? "Connected" : "Not confirmed"} ok={readiness.cdas.provider_tested} />
                <StateRow label="Employee verified" value={readiness.cdas.verified ? "Yes" : "No"} ok={readiness.cdas.verified} />
                <StateRow label="Employee No" value={readiness.cdas.employee_number ?? "—"} />
                <StateRow label="Department" value={readiness.cdas.department ?? "—"} />
              </>
            ) : null}
            <Button variant="outline" className="w-full" asChild>
              <Link href={`/company/cdas?application=${application.id}`}>Open CDAS evidence</Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      {(readiness.blockers.length > 0 || readiness.warnings.length > 0) ? (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card className="rounded-3xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-destructive" />Approval blockers</CardTitle>
              <CardDescription>These must be resolved before normal approval.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {readiness.blockers.length === 0 ? <p className="text-sm text-muted-foreground">No blockers.</p> : readiness.blockers.map((item) => (
                <div key={`${item.source}:${item.code}`} className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4">
                  <p className="font-black">{titleCase(item.source)} · {titleCase(item.code)}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{item.message}</p>
                  <Button size="sm" variant="outline" className="mt-3" asChild><Link href={item.action_path}>Resolve</Link></Button>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="rounded-3xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Gauge className="h-5 w-5 text-amber-600" />Warnings and review</CardTitle>
              <CardDescription>These do not always block the loan, but should be reviewed.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {readiness.warnings.length === 0 ? <p className="text-sm text-muted-foreground">No warnings.</p> : readiness.warnings.map((item) => (
                <div key={`${item.source}:${item.code}`} className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
                  <p className="font-black">{titleCase(item.source)} · {titleCase(item.code)}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{item.message}</p>
                  <Button size="sm" variant="outline" className="mt-3" asChild><Link href={item.action_path}>Review</Link></Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      ) : (
        <Alert>
          <CheckCircle2 className="h-4 w-4" />
          <AlertTitle>Systems agree</AlertTitle>
          <AlertDescription>Core LoanHub, the applicable Experian rules and CDAS collection requirements have no outstanding blocker for this application.</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><WalletCards className="h-5 w-5 text-primary" />Affordability explanation</CardTitle>
            <CardDescription>The reasons recorded by the affordability engine remain visible even after an override.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {assessment?.result_reasons?.length ? assessment.result_reasons.map((reason) => (
              <div key={reason.code} className="flex gap-3 rounded-2xl border p-3">
                {reason.severity === "error" ? <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" /> : <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />}
                <div>
                  <p className="text-sm font-black">{titleCase(reason.code)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{reason.message}</p>
                </div>
              </div>
            )) : <p className="text-sm text-muted-foreground">No affordability assessment has been recorded yet.</p>}
            {assessment?.overridden ? (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Management override recorded</AlertTitle>
                <AlertDescription>{assessment.override_reason || "An affordability decision override was recorded."}</AlertDescription>
              </Alert>
            ) : null}
          </CardContent>
        </Card>

        <Card className="rounded-3xl">
          <CardHeader>
            <CardTitle>Decision evidence timeline</CardTitle>
            <CardDescription>Chronological evidence currently available for this application.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {timeline.map((item, index) => <TimelineRow key={`${item.title}:${index}`} {...item} />)}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
