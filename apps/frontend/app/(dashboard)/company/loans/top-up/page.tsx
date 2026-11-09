"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { getLoan } from "@/api/loans";
import { originationApi } from "@/api/origination";
import { CompactTopUpDialog } from "@/components/loans/compact-top-up-dialog";
import { Button } from "@/components/ui/button";
import { useTenant } from "@/provider/tenantProvider";
import { formatMoney } from "@/lib/format";
import type { Loan } from "@/types/loan";
import type { OriginationApplication } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

export default function DirectLoanTopUpPage() {
  return <Suspense fallback={<div className="p-6">Loading loan top-up…</div>}><TopUpWorkspace /></Suspense>;
}

function TopUpWorkspace() {
  const search = useSearchParams();
  const router = useRouter();
  const { activeRole } = useTenant();
  const loanId = search.get("loan");
  const applicationId = search.get("application");
  const [loan, setLoan] = useState<Loan | null>(null);
  const [application, setApplication] = useState<OriginationApplication | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const canManage = activeRole === "company_owner" || activeRole === "branch_manager";

  useEffect(() => {
    let current = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const draft = applicationId ? (await originationApi.getWorkspace(applicationId)).application : null;
        if (draft && draft.application_type !== "top_up") {
          router.replace(`/company/origination/new?application=${encodeURIComponent(draft.id)}`);
          return;
        }
        const parentId = draft?.parent_loan_id ?? loanId;
        if (!parentId) throw new Error("Choose an existing loan from Loans & Contracts to begin a top-up.");
        const parent = await getLoan(parentId);
        if (draft && draft.borrower_id !== parent.borrower_id) throw new Error("The selected top-up does not belong to this borrower.");
        if (!current) return;
        setLoan(parent);
        setApplication(draft);
        if (!draft) {
          const pending = (await originationApi.listApplications()).find(
            (item) => item.application_type === "top_up" &&
              item.parent_loan_id === parent.id &&
              ["draft", "submitted", "under_review"].includes(item.status)
          );
          if (pending) {
            router.replace(`/company/loans/top-up?application=${encodeURIComponent(pending.id)}`);
            return;
          }
        }
      } catch (cause: unknown) {
        if (current) setError(getErrorMessage(cause, "Could not load the existing loan."));
      } finally {
        if (current) setLoading(false);
      }
    }
    void load();
    return () => { current = false; };
  }, [applicationId, loanId, router]);

  async function approveException() {
    if (!application || activeRole !== "company_owner") return;
    const reason = window.prompt("Company-owner top-up exception reason (minimum 10 characters):");
    if (!reason || reason.trim().length < 10) return;
    setSaving(true);
    try {
      const result = await originationApi.approveTopUpException(application.id, reason.trim());
      setApplication(result);
      toast.success("Top-up exception approved");
    } catch (cause: unknown) {
      toast.error(getErrorMessage(cause, "Could not approve this top-up exception."));
    } finally { setSaving(false); }
  }

  async function submitForApproval() {
    if (!application || application.status !== "draft") return;
    setSaving(true);
    try {
      const result = await originationApi.submit(application.id);
      setApplication(result);
      toast.success("Top-up submitted for management approval");
    } catch (cause: unknown) {
      toast.error(getErrorMessage(cause, "Top-up could not be submitted. Check the displayed approval requirements."));
    } finally { setSaving(false); }
  }

  if (loading) return <div className="loanhub-page"><div className="rounded-2xl border bg-card p-6">Loading top-up information…</div></div>;

  return <main className="loanhub-page space-y-5">
    <section className="loanhub-hero p-6 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">Loans &amp; Contracts / Direct top-up</p>
          <h1 className="mt-2 text-3xl font-black">Top up existing loan</h1>
          <p className="mt-2 text-sm text-muted-foreground">A direct loan action — no credit origination wizard or affordability assessment.</p>
        </div>
        <Button variant="outline" asChild><Link href="/company/loans"><ArrowLeft className="mr-2 h-4 w-4" />Back to loans</Link></Button>
      </div>
    </section>
    {error ? <div role="alert" className="rounded-2xl border border-destructive/30 bg-destructive/5 p-5 text-destructive">{error}</div> : null}
    {loan && !error ? <>
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border bg-card p-5"><p className="text-xs text-muted-foreground">Existing loan</p><p className="mt-2 font-bold">{loan.loan_reference}</p></div>
        <div className="rounded-2xl border bg-card p-5"><p className="text-xs text-muted-foreground">Outstanding balance</p><p className="mt-2 font-bold">{formatMoney(Number(loan.balance))}</p></div>
        <div className="rounded-2xl border bg-card p-5"><p className="text-xs text-muted-foreground">Current status</p><p className="mt-2 font-bold">{loan.status}</p></div>
      </section>
      {!canManage ? <div role="alert" className="rounded-xl border p-5">Only a company owner or branch manager can create a loan top-up.</div> : application ? (
        <section className="space-y-4 rounded-3xl border bg-card p-6">
          <div>
            <h2 className="text-xl font-bold">Top-up application {application.application_reference}</h2>
            <p className="mt-1 text-sm text-muted-foreground">Status: {application.status}. This is a replacement-loan application linked to the original loan.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div><p className="text-xs text-muted-foreground">Additional cash requested</p><p className="font-semibold">{formatMoney(Number(application.top_up_cash_requested ?? 0))}</p></div>
            <div><p className="text-xs text-muted-foreground">Replacement principal</p><p className="font-semibold">{formatMoney(Number(application.requested_amount))}</p></div>
            <div><p className="text-xs text-muted-foreground">Repayment period</p><p className="font-semibold">{application.term_count} months</p></div>
          </div>
          {application.top_up_exception_requested && !application.top_up_exception_approved ? (
            <div className="space-y-2 rounded-xl border border-amber-500/40 p-4">
              <p className="font-semibold">Company-owner top-up exception required</p>
              <p className="text-sm">Repayment threshold exception must be authorised separately; it is not an affordability assessment.</p>
              {activeRole === "company_owner" ? <Button type="button" disabled={saving} onClick={() => void approveException()}>Approve exception</Button> : <p className="text-sm">Ask the company owner to approve the exception.</p>}
            </div>
          ) : null}
          <p className="text-sm text-muted-foreground">KYC verification is optional when submitting a top-up for management review. Company policy, verified CDAS payroll requirements when selected, management approval, contract and disbursement controls still apply.</p>
          <div className="flex flex-wrap gap-3">
            {application.status === "draft" ? <Button disabled={saving || (application.top_up_exception_requested && !application.top_up_exception_approved)} onClick={() => void submitForApproval()}><CheckCircle2 className="mr-2 h-4 w-4" />Submit for management approval</Button> : null}
            <Button variant="outline" asChild><Link href={`/company/marketplace?workspace=applications&application=${encodeURIComponent(application.id)}`}>Open approval workspace</Link></Button>
          </div>
        </section>
      ) : ["active", "defaulted"].includes(loan.status) ? (
        <CompactTopUpDialog loan={loan} inline onClose={() => router.push("/company/loans")} onCreated={(id) => router.replace(`/company/loans/top-up?application=${encodeURIComponent(id)}`)} />
      ) : <div className="rounded-xl border bg-card p-5">This loan is not eligible for a top-up in its current state.</div>}
    </> : null}
  </main>;
}
