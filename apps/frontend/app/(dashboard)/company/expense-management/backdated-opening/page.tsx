"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ArrowLeft, CalendarClock, CheckCircle2, ShieldCheck } from "lucide-react";

import { expenseManagementApi } from "@/api/expenseManagement";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";
import type {
  BackdatedOpeningAdjustmentCreate,
  BackdatedOpeningAdjustmentResult,
  BackdatedOpeningSourceType,
} from "@/types/backdatedOpeningAdjustment";
import type { PaymentMethod, PaymentMethodOption } from "@/types/expenseManagement";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const localIsoDate = (offsetDays = 0) => {
  const value = new Date();
  value.setDate(value.getDate() + offsetDays);
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
};

const SOURCE_OPTIONS: Array<{ value: BackdatedOpeningSourceType; label: string }> = [
  { value: "opening_adjustment", label: "Historical opening adjustment" },
  { value: "cash_float", label: "Cash float" },
  { value: "bank_float", label: "Bank float" },
  { value: "retained_funds", label: "Retained funds" },
  { value: "owner_contribution", label: "Owner contribution" },
  { value: "other", label: "Other genuine source" },
];

const formatAmount = (value: number | string | null | undefined, currency = "LSL") =>
  formatMoney(Number(value ?? 0), currency);

export default function BackdatedOpeningAdjustmentPage() {
  const { branches } = useAppData();
  const { activeBranchId, activeRole } = useTenant();
  const canManageCompany = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
  const canUseHistoricalCorrection = canManageCompany || activeRole === "finance_officer";
  const yesterday = localIsoDate(-1);

  const [working, setWorking] = useState(false);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodOption[]>([]);
  const [result, setResult] = useState<BackdatedOpeningAdjustmentResult | null>(null);
  const [form, setForm] = useState<BackdatedOpeningAdjustmentCreate>({
    branch_id: activeBranchId ?? undefined,
    business_date: yesterday,
    source_type: "opening_adjustment",
    payment_method: "cash",
    amount: "",
    currency: "LSL",
    description: "",
    correction_reason: "",
    source_reference: "",
    proof_reference: "",
    proof_url: "",
    proof_notes: "",
  });

  useEffect(() => {
    if (!form.branch_id && branches.length > 0) {
      setForm((current) => ({ ...current, branch_id: activeBranchId ?? branches[0]?.id }));
    }
  }, [activeBranchId, branches, form.branch_id]);

  useEffect(() => {
    let cancelled = false;
    void expenseManagementApi.paymentMethods()
      .then((items) => {
        if (!cancelled) setPaymentMethods(items);
      })
      .catch(() => {
        if (!cancelled) setPaymentMethods([{ value: "cash", label: "Cash", proof_recommended: false }]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedBranchName = useMemo(
    () => branches.find((branch) => branch.id === form.branch_id)?.name ?? "Selected branch",
    [branches, form.branch_id],
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setResult(null);

    if (!form.branch_id) {
      toast.error("Select the branch whose historical opening funds are being corrected");
      return;
    }
    if (!form.business_date || form.business_date > yesterday) {
      toast.error("Choose a business date before today");
      return;
    }
    if (Number(form.amount) <= 0) {
      toast.error("Enter the actual opening amount that existed on that date");
      return;
    }
    if (form.correction_reason.trim().length < 10) {
      toast.error("Explain why the opening funds were omitted; use at least 10 characters");
      return;
    }

    setWorking(true);
    try {
      const created = await expenseManagementApi.createBackdatedOpeningAdjustment({
        ...form,
        branch_id: form.branch_id,
        description: form.description.trim(),
        correction_reason: form.correction_reason.trim(),
        source_reference: form.source_reference?.trim() || undefined,
        proof_reference: form.proof_reference?.trim() || undefined,
        proof_url: form.proof_url?.trim() || undefined,
        proof_notes: form.proof_notes?.trim() || undefined,
      });
      setResult(created);
      toast.success("Historical opening source recorded and carry-forward recalculated");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The back-dated opening correction could not be recorded"));
    } finally {
      setWorking(false);
    }
  }

  if (!canUseHistoricalCorrection) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-6 p-4 sm:p-6 lg:p-8">
        <Button asChild variant="outline"><Link href="/company/expense-management"><ArrowLeft className="mr-2 h-4 w-4" />Back to Payments & finance</Link></Button>
        <Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Finance permission required</AlertTitle><AlertDescription>Only company management and finance officers can record historical opening corrections.</AlertDescription></Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground"><CalendarClock className="h-4 w-4" />Payments & finance</div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Back-dated opening balance</h1>
          <p className="max-w-3xl text-sm text-muted-foreground sm:text-base">Record money that genuinely existed at the start of a past business day but was omitted from LoanHub. The system journals the source, preserves the audit trail and recalculates later carry-forward balances.</p>
        </div>
        <Button asChild variant="outline"><Link href="/company/expense-management"><ArrowLeft className="mr-2 h-4 w-4" />Money management</Link></Button>
      </div>

      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>This is an audited correction, not a balance override</AlertTitle>
        <AlertDescription>Enter only funds that actually existed on the selected date. Submitted days are revised without deleting the original submission. Existing physical closing counts remain audit anchors unless deliberately corrected through the controlled workflow.</AlertDescription>
      </Alert>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader><CardTitle>Historical opening source</CardTitle><CardDescription>Choose the original date and identify where the funds actually came from.</CardDescription></CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Branch">
                  <Select value={form.branch_id ?? ""} onValueChange={(value) => setForm((current) => ({ ...current, branch_id: value }))} disabled={!canManageCompany && Boolean(activeBranchId)}>
                    <SelectTrigger><SelectValue placeholder="Select branch" /></SelectTrigger>
                    <SelectContent>{branches.map((branch) => <SelectItem key={branch.id} value={branch.id}>{branch.name}</SelectItem>)}</SelectContent>
                  </Select>
                </Field>
                <Field label="Business date">
                  <Input required type="date" max={yesterday} value={form.business_date} onChange={(event) => setForm((current) => ({ ...current, business_date: event.target.value }))} />
                </Field>
                <Field label="Actual source of opening funds">
                  <Select value={form.source_type} onValueChange={(value) => setForm((current) => ({ ...current, source_type: value as BackdatedOpeningSourceType }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{SOURCE_OPTIONS.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
                  </Select>
                </Field>
                <Field label="Payment channel">
                  <Select value={form.payment_method} onValueChange={(value) => setForm((current) => ({ ...current, payment_method: value as PaymentMethod }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{paymentMethods.map((method) => <SelectItem key={method.value} value={method.value}>{method.label}</SelectItem>)}</SelectContent>
                  </Select>
                </Field>
                <Field label="Amount">
                  <Input required type="number" min="0.01" step="0.01" inputMode="decimal" value={form.amount} onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))} placeholder="31331.20" />
                </Field>
                <Field label="Source reference (optional)">
                  <Input value={form.source_reference ?? ""} onChange={(event) => setForm((current) => ({ ...current, source_reference: event.target.value }))} placeholder="Cash count, bank slip or internal reference" />
                </Field>
              </div>

              <Field label="Actual source description">
                <Input required minLength={3} value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} placeholder="Opening cash float available before loan disbursements" />
              </Field>

              <Field label="Why is this being corrected now?">
                <Textarea required minLength={10} rows={4} value={form.correction_reason} onChange={(event) => setForm((current) => ({ ...current, correction_reason: event.target.value }))} placeholder="Opening cash existed on 25 Sep but was omitted before the day's loan disbursements were recorded." />
              </Field>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Proof/reference number (optional)">
                  <Input value={form.proof_reference ?? ""} onChange={(event) => setForm((current) => ({ ...current, proof_reference: event.target.value }))} placeholder="Till count, receipt or statement reference" />
                </Field>
                <Field label="Proof document URL (optional)">
                  <Input type="url" value={form.proof_url ?? ""} onChange={(event) => setForm((current) => ({ ...current, proof_url: event.target.value }))} placeholder="https://..." />
                </Field>
              </div>
              <Field label="Evidence notes (optional)">
                <Textarea rows={3} value={form.proof_notes ?? ""} onChange={(event) => setForm((current) => ({ ...current, proof_notes: event.target.value }))} placeholder="Describe the cash count or supporting record used to verify this opening amount." />
              </Field>

              <div className="flex flex-col gap-3 rounded-xl border bg-muted/30 p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
                <div><p className="font-medium">Correction will apply to {selectedBranchName}</p><p className="text-muted-foreground">Later daily ledgers will be refreshed from this historical date forward.</p></div>
                <LoadingButton type="submit" loading={working}>Record & recalculate</LoadingButton>
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-base">What LoanHub will do</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>1. Add the genuine historical opening source.</p>
              <p>2. Create the corresponding balanced accounting journal.</p>
              <p>3. Recalculate the selected business day.</p>
              <p>4. Preserve old submitted snapshots and create a corrected revision where required.</p>
              <p>5. Refresh later carry-forward balances, including the current day.</p>
            </CardContent>
          </Card>

          {result ? (
            <Card className="border-emerald-200">
              <CardHeader><div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-emerald-600" /><CardTitle className="text-base">Correction completed</CardTitle></div><CardDescription>{result.business_date} · {result.source_reference}</CardDescription></CardHeader>
              <CardContent className="space-y-4 text-sm">
                <ResultRow label="Historical opening" before={formatAmount(result.old_opening_balance)} after={formatAmount(result.new_opening_balance)} />
                <ResultRow label="Historical expected closing" before={formatAmount(result.old_expected_closing_balance)} after={formatAmount(result.new_expected_closing_balance)} />
                <div className="rounded-lg bg-muted/40 p-3"><p className="text-muted-foreground">Current opening after carry-forward</p><p className="mt-1 text-lg font-semibold">{result.current_opening_balance == null ? "No current ledger" : formatAmount(result.current_opening_balance)}</p></div>
                <p className="text-muted-foreground">{result.downstream_days_refreshed} downstream day(s) refreshed; {result.downstream_days_revised} submitted day(s) received a new revision.</p>
                <Button asChild className="w-full"><Link href="/company/expense-management">View recalculated Money Management</Link></Button>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function ResultRow({ label, before, after }: { label: string; before: string; after: string }) {
  return <div className="rounded-lg border p-3"><p className="font-medium">{label}</p><div className="mt-2 grid grid-cols-2 gap-2"><div><p className="text-xs text-muted-foreground">Before</p><p>{before}</p></div><div><p className="text-xs text-muted-foreground">After</p><p className="font-semibold">{after}</p></div></div></div>;
}
