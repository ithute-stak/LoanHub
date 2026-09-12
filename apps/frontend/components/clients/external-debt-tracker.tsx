"use client";

import { useMemo, useState, type ReactNode } from "react";
import {
  BadgeCheck,
  Banknote,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  History,
  Landmark,
  Pencil,
  Plus,
  ReceiptText,
  ShieldAlert,
} from "lucide-react";

import {
  createCompanyClientExternalDebt,
  recordCompanyClientExternalDebtPayment,
  updateCompanyClientExternalDebt,
} from "@/api/companyClients";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import type {
  CompanyClientExternalDebt,
  CompanyClientExternalDebtInput,
  ExternalDebtFrequency,
  ExternalDebtStatus,
} from "@/types/companyClient";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const ACTIVE_STATUSES = new Set<ExternalDebtStatus>(["active", "defaulted", "restructured", "unknown"]);
const FREQUENCIES: ExternalDebtFrequency[] = ["weekly", "fortnightly", "monthly", "quarterly", "custom"];
const STATUSES: ExternalDebtStatus[] = ["active", "restructured", "defaulted", "settled", "written_off", "unknown"];

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function emptyDebt(): CompanyClientExternalDebtInput {
  return {
    creditor: "",
    account_reference: null,
    debt_type: "personal_loan",
    started_on: null,
    original_amount: 0,
    current_balance: 0,
    installment_amount: 0,
    installment_frequency: "monthly",
    total_installments: null,
    installments_paid: 0,
    remaining_installments: null,
    next_due_date: null,
    status: "active",
    source: "declared",
    is_verified: false,
    notes: null,
  };
}

function debtDraft(row: CompanyClientExternalDebt): CompanyClientExternalDebtInput {
  return {
    creditor: row.creditor,
    account_reference: row.account_reference,
    debt_type: row.debt_type,
    started_on: row.started_on,
    original_amount: Number(row.original_amount || 0),
    current_balance: Number(row.current_balance || 0),
    installment_amount: Number(row.installment_amount || 0),
    installment_frequency: row.installment_frequency,
    total_installments: row.total_installments,
    installments_paid: Number(row.installments_paid || 0),
    remaining_installments: row.remaining_installments,
    next_due_date: row.next_due_date,
    status: row.status,
    source: row.source,
    is_verified: row.is_verified,
    notes: row.notes,
  };
}

function optional(value: string | null | undefined) {
  const cleaned = String(value ?? "").trim();
  return cleaned || null;
}

function activeDebt(row: CompanyClientExternalDebt) {
  return ACTIVE_STATUSES.has(row.status) && Number(row.current_balance || 0) > 0;
}

function installmentText(row: CompanyClientExternalDebt) {
  if (Number(row.installment_amount || 0) <= 0) return "Schedule not supplied";
  return `${formatMoney(row.installment_amount)} ${titleCase(row.installment_frequency)}`;
}

function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return <div className={`space-y-1.5 ${className}`}><Label>{label}</Label>{children}</div>;
}

function Metric({ icon: Icon, label, value, note }: { icon: typeof Landmark; label: string; value: string; note: string }) {
  return (
    <Card className="rounded-2xl shadow-none">
      <CardContent className="flex items-start gap-3 p-4">
        <div className="rounded-xl bg-primary/10 p-2.5 text-primary"><Icon className="h-4 w-4" /></div>
        <div className="min-w-0"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">{label}</p><p className="mt-1 text-lg font-black">{value}</p><p className="mt-1 text-xs text-muted-foreground">{note}</p></div>
      </CardContent>
    </Card>
  );
}

export function ExternalDebtTracker({
  accountId,
  debts,
  canEdit,
  onChanged,
}: {
  accountId: string;
  debts: CompanyClientExternalDebt[];
  canEdit: boolean;
  onChanged: (debts: CompanyClientExternalDebt[]) => void;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CompanyClientExternalDebt | null>(null);
  const [draft, setDraft] = useState<CompanyClientExternalDebtInput>(emptyDebt());
  const [saving, setSaving] = useState(false);
  const [paymentDebt, setPaymentDebt] = useState<CompanyClientExternalDebt | null>(null);
  const [payment, setPayment] = useState({ amount: 0, paid_on: todayIso(), installments_covered: 1, next_due_date: "", notes: "" });
  const [recordingPayment, setRecordingPayment] = useState(false);
  const [historyDebtId, setHistoryDebtId] = useState<string | null>(null);

  const active = useMemo(() => debts.filter(activeDebt), [debts]);
  const balanceTotal = useMemo(() => active.reduce((sum, row) => sum + Number(row.current_balance || 0), 0), [active]);
  const monthlyCommitment = useMemo(() => active.reduce((sum, row) => sum + Number(row.monthly_installment || 0), 0), [active]);

  function openCreate() {
    setEditing(null);
    setDraft(emptyDebt());
    setDialogOpen(true);
  }

  function openEdit(row: CompanyClientExternalDebt) {
    setEditing(row);
    setDraft(debtDraft(row));
    setDialogOpen(true);
  }

  function updateDraft<K extends keyof CompanyClientExternalDebtInput>(key: K, value: CompanyClientExternalDebtInput[K]) {
    setDraft((current) => {
      const next = { ...current, [key]: value };
      if ((key === "total_installments" || key === "installments_paid") && next.total_installments !== null && next.total_installments !== undefined) {
        next.remaining_installments = Math.max(Number(next.total_installments) - Number(next.installments_paid || 0), 0);
      }
      return next;
    });
  }

  async function saveDebt() {
    if (!draft.creditor.trim()) {
      toast.warning("Enter the lender or creditor name.");
      return;
    }
    if (draft.started_on && draft.started_on > todayIso()) {
      toast.warning("The external loan start date cannot be in the future.");
      return;
    }
    if (ACTIVE_STATUSES.has(draft.status ?? "active") && Number(draft.current_balance || 0) > 0 && Number(draft.installment_amount || 0) <= 0) {
      toast.warning("Enter the installment amount for this active external loan.");
      return;
    }

    setSaving(true);
    try {
      const payload: CompanyClientExternalDebtInput = {
        ...draft,
        creditor: draft.creditor.trim(),
        account_reference: optional(draft.account_reference),
        debt_type: draft.debt_type || "other",
        started_on: optional(draft.started_on),
        original_amount: Number(draft.original_amount || 0),
        current_balance: Number(draft.current_balance || 0),
        installment_amount: Number(draft.installment_amount || 0),
        total_installments: draft.total_installments === null || draft.total_installments === undefined ? null : Number(draft.total_installments),
        installments_paid: Number(draft.installments_paid || 0),
        remaining_installments: draft.remaining_installments === null || draft.remaining_installments === undefined ? null : Number(draft.remaining_installments),
        next_due_date: optional(draft.next_due_date),
        source: draft.source || "declared",
        notes: optional(draft.notes),
      };
      const saved = editing
        ? await updateCompanyClientExternalDebt(accountId, editing.id, payload)
        : await createCompanyClientExternalDebt(accountId, payload);
      const next = editing
        ? debts.map((row) => row.id === saved.id ? saved : row)
        : [saved, ...debts];
      onChanged(next);
      setDialogOpen(false);
      setEditing(null);
      toast.success(editing ? "External loan updated." : "External loan added to the borrower tracker.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The external loan could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  function openPayment(row: CompanyClientExternalDebt) {
    setPaymentDebt(row);
    setPayment({
      amount: Math.min(Number(row.installment_amount || 0), Number(row.current_balance || 0)),
      paid_on: todayIso(),
      installments_covered: 1,
      next_due_date: row.next_due_date ?? "",
      notes: "",
    });
  }

  async function savePayment() {
    if (!paymentDebt) return;
    if (Number(payment.amount || 0) <= 0) {
      toast.warning("Enter the payment amount.");
      return;
    }
    setRecordingPayment(true);
    try {
      const saved = await recordCompanyClientExternalDebtPayment(accountId, paymentDebt.id, {
        amount: Number(payment.amount),
        paid_on: payment.paid_on,
        installments_covered: Number(payment.installments_covered || 0),
        next_due_date: optional(payment.next_due_date),
        notes: optional(payment.notes),
      });
      onChanged(debts.map((row) => row.id === saved.id ? saved : row));
      setPaymentDebt(null);
      toast.success("External loan payment recorded and the remaining schedule updated.");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The external loan payment could not be recorded."));
    } finally {
      setRecordingPayment(false);
    }
  }

  return (
    <>
      <Card className="overflow-hidden rounded-2xl shadow-none">
        <CardHeader className="gap-4 border-b bg-muted/20 sm:flex-row sm:items-start sm:justify-between">
          <div><CardTitle className="flex items-center gap-2 text-base"><Landmark className="h-4 w-4 text-primary" />Tracked external loans</CardTitle><p className="mt-1 text-sm text-muted-foreground">These obligations remain attached to the borrower and are reused in later affordability assessments.</p></div>
          {canEdit ? <Button type="button" size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add existing loan</Button> : null}
        </CardHeader>
        <CardContent className="space-y-5 p-4 sm:p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <Metric icon={ReceiptText} label="Active external loans" value={String(active.length)} note={`${debts.length} total tracked record${debts.length === 1 ? "" : "s"}`} />
            <Metric icon={CircleDollarSign} label="External balance" value={formatMoney(balanceTotal)} note="Included in the borrower’s total exposure" />
            <Metric icon={CalendarClock} label="Monthly commitment" value={formatMoney(monthlyCommitment)} note="Used by affordability calculations" />
          </div>

          {debts.length === 0 ? (
            <Alert><ShieldAlert className="h-4 w-4" /><AlertTitle>No external loans recorded</AlertTitle><AlertDescription>Add each debt separately so LoanHub can remember when it began, its installment amount, and how many installments remain.</AlertDescription></Alert>
          ) : (
            <div className="space-y-3">
              {debts.map((row) => {
                const showHistory = historyDebtId === row.id;
                return (
                  <div key={row.id} className="overflow-hidden rounded-2xl border bg-card">
                    <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1.5fr)_repeat(3,minmax(130px,0.65fr))_auto] lg:items-center">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2"><p className="truncate font-black">{row.creditor}</p><Badge variant={row.status === "settled" ? "secondary" : row.status === "defaulted" ? "destructive" : "outline"}>{titleCase(row.status)}</Badge>{row.is_verified ? <Badge className="gap-1" variant="secondary"><BadgeCheck className="h-3 w-3" />Verified</Badge> : null}</div>
                        <p className="mt-1 text-xs text-muted-foreground">{titleCase(row.debt_type)}{row.account_reference ? ` · ${row.account_reference}` : ""}</p>
                        <p className="mt-1 text-xs text-muted-foreground">Since {row.started_on ? formatDate(row.started_on) : "date not recorded"}</p>
                      </div>
                      <div><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Balance</p><p className="mt-1 font-black">{formatMoney(row.current_balance)}</p><p className="text-xs text-muted-foreground">Original {formatMoney(row.original_amount)}</p></div>
                      <div><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Installment</p><p className="mt-1 font-black">{installmentText(row)}</p><p className="text-xs text-muted-foreground">Monthly equivalent {formatMoney(row.monthly_installment)}</p></div>
                      <div><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Remaining</p><p className="mt-1 font-black">{row.remaining_installments ?? "—"} installment{row.remaining_installments === 1 ? "" : "s"}</p><p className="text-xs text-muted-foreground">Next {row.next_due_date ? formatDate(row.next_due_date) : "date not supplied"}</p></div>
                      <div className="flex flex-wrap gap-2 lg:justify-end">
                        <Button type="button" size="sm" variant="outline" onClick={() => setHistoryDebtId(showHistory ? null : row.id)}><History className="h-3.5 w-3.5" />History</Button>
                        {canEdit ? <Button type="button" size="sm" variant="outline" onClick={() => openEdit(row)}><Pencil className="h-3.5 w-3.5" />Edit</Button> : null}
                        {canEdit && activeDebt(row) ? <Button type="button" size="sm" onClick={() => openPayment(row)}><Banknote className="h-3.5 w-3.5" />Payment</Button> : null}
                      </div>
                    </div>
                    {showHistory ? (
                      <div className="border-t bg-muted/15 p-4">
                        <p className="mb-3 flex items-center gap-2 text-sm font-black"><Clock3 className="h-4 w-4 text-primary" />Tracking history</p>
                        <div className="space-y-2">
                          {[...row.events].reverse().map((event) => (
                            <div key={event.id} className="grid gap-1 rounded-xl border bg-background p-3 text-sm sm:grid-cols-[150px_130px_minmax(0,1fr)]">
                              <div><p className="font-bold">{titleCase(event.event_type)}</p><p className="text-xs text-muted-foreground">{new Date(event.event_at).toLocaleString()}</p></div>
                              <div><p className="font-semibold">{event.amount === null ? "—" : formatMoney(event.amount)}</p><p className="text-xs text-muted-foreground">Balance {event.balance_after === null ? "—" : formatMoney(event.balance_after)}</p></div>
                              <p className="text-xs leading-5 text-muted-foreground">{event.notes || `${event.remaining_installments_after ?? "—"} installments remaining`}</p>
                            </div>
                          ))}
                          {row.events.length === 0 ? <p className="text-sm text-muted-foreground">No tracking events are available yet.</p> : null}
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) setEditing(null); }}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-4xl">
          <DialogHeader><DialogTitle>{editing ? "Review external loan" : "Add existing external loan"}</DialogTitle><DialogDescription>Record the balance and full installment schedule. LoanHub will carry this commitment into later affordability checks.</DialogDescription></DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Lender or creditor"><Input value={draft.creditor} onChange={(event) => updateDraft("creditor", event.target.value)} /></Field>
            <Field label="Account reference"><Input value={draft.account_reference ?? ""} onChange={(event) => updateDraft("account_reference", event.target.value)} /></Field>
            <Field label="Debt type"><Input value={draft.debt_type ?? ""} onChange={(event) => updateDraft("debt_type", event.target.value)} placeholder="Personal loan, store account..." /></Field>
            <Field label="Loan started"><Input type="date" max={todayIso()} value={draft.started_on ?? ""} onChange={(event) => updateDraft("started_on", event.target.value || null)} /></Field>
            <Field label="Original amount"><Input type="number" min="0" step="0.01" value={draft.original_amount} onChange={(event) => updateDraft("original_amount", Number(event.target.value || 0))} /></Field>
            <Field label="Current balance"><Input type="number" min="0" step="0.01" value={draft.current_balance} onChange={(event) => updateDraft("current_balance", Number(event.target.value || 0))} /></Field>
            <Field label="Installment amount"><Input type="number" min="0" step="0.01" value={draft.installment_amount} onChange={(event) => updateDraft("installment_amount", Number(event.target.value || 0))} /></Field>
            <Field label="Installment frequency"><Select value={draft.installment_frequency} onValueChange={(value) => updateDraft("installment_frequency", value as ExternalDebtFrequency)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{FREQUENCIES.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select></Field>
            <Field label="Status"><Select value={draft.status ?? "active"} onValueChange={(value) => updateDraft("status", value as ExternalDebtStatus)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{STATUSES.map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select></Field>
            <Field label="Total installments"><Input type="number" min="0" step="1" value={draft.total_installments ?? ""} onChange={(event) => updateDraft("total_installments", event.target.value === "" ? null : Number(event.target.value))} /></Field>
            <Field label="Installments paid"><Input type="number" min="0" step="1" value={draft.installments_paid ?? 0} onChange={(event) => updateDraft("installments_paid", Number(event.target.value || 0))} /></Field>
            <Field label="Installments remaining"><Input type="number" min="0" step="1" value={draft.remaining_installments ?? ""} onChange={(event) => updateDraft("remaining_installments", event.target.value === "" ? null : Number(event.target.value))} /></Field>
            <Field label="Next due date"><Input type="date" value={draft.next_due_date ?? ""} onChange={(event) => updateDraft("next_due_date", event.target.value || null)} /></Field>
            <Field label="Source"><Input value={draft.source ?? "declared"} onChange={(event) => updateDraft("source", event.target.value)} /></Field>
            <label className="flex items-center gap-3 rounded-xl border p-3 lg:mt-6"><Checkbox checked={draft.is_verified === true} onCheckedChange={(checked) => updateDraft("is_verified", checked === true)} /><span className="text-sm font-bold">Supporting evidence verified</span></label>
            <Field label="Notes" className="sm:col-span-2 lg:col-span-3"><Textarea rows={3} value={draft.notes ?? ""} onChange={(event) => updateDraft("notes", event.target.value)} /></Field>
          </div>
          <DialogFooter><Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button><LoadingButton loading={saving} loadingText="Saving external loan..." onClick={() => void saveDebt()}><CheckCircle2 className="h-4 w-4" />Save tracked loan</LoadingButton></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={paymentDebt !== null} onOpenChange={(open) => { if (!open) setPaymentDebt(null); }}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader><DialogTitle>Record external loan payment</DialogTitle><DialogDescription>{paymentDebt ? `${paymentDebt.creditor} · balance ${formatMoney(paymentDebt.current_balance)}` : "Update the borrower’s external obligation."}</DialogDescription></DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Payment amount"><Input type="number" min="0.01" step="0.01" value={payment.amount} onChange={(event) => setPayment((current) => ({ ...current, amount: Number(event.target.value || 0) }))} /></Field>
            <Field label="Payment date"><Input type="date" max={todayIso()} value={payment.paid_on} onChange={(event) => setPayment((current) => ({ ...current, paid_on: event.target.value }))} /></Field>
            <Field label="Installments covered"><Input type="number" min="0" step="1" value={payment.installments_covered} onChange={(event) => setPayment((current) => ({ ...current, installments_covered: Number(event.target.value || 0) }))} /></Field>
            <Field label="Next due date"><Input type="date" value={payment.next_due_date} onChange={(event) => setPayment((current) => ({ ...current, next_due_date: event.target.value }))} /></Field>
            <Field label="Payment note" className="sm:col-span-2"><Textarea rows={3} value={payment.notes} onChange={(event) => setPayment((current) => ({ ...current, notes: event.target.value }))} placeholder="Receipt/reference or borrower confirmation" /></Field>
          </div>
          <Separator />
          <DialogFooter><Button type="button" variant="outline" onClick={() => setPaymentDebt(null)}>Cancel</Button><LoadingButton loading={recordingPayment} loadingText="Recording payment..." onClick={() => void savePayment()}><Banknote className="h-4 w-4" />Record payment</LoadingButton></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
