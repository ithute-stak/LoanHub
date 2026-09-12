"use client";

import type { ReactNode } from "react";
import { Plus, Trash2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatMoney, titleCase } from "@/lib/format";
import type {
  CompanyClientExternalDebtInput,
  ExternalDebtFrequency,
  ExternalDebtStatus,
} from "@/types/companyClient";

const ACTIVE_STATUSES = new Set<ExternalDebtStatus>(["active", "defaulted", "restructured", "unknown"]);
const MONTHLY_FACTORS: Record<ExternalDebtFrequency, number> = {
  weekly: 52 / 12,
  fortnightly: 26 / 12,
  monthly: 1,
  quarterly: 1 / 3,
  custom: 1,
};

export function blankExternalDebt(): CompanyClientExternalDebtInput {
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

export function activeExternalDebtBalance(debts: CompanyClientExternalDebtInput[]) {
  return debts.reduce((sum, row) => {
    const status = row.status ?? "active";
    return ACTIVE_STATUSES.has(status) ? sum + Number(row.current_balance || 0) : sum;
  }, 0);
}

export function monthlyExternalDebtCommitment(debts: CompanyClientExternalDebtInput[]) {
  return debts.reduce((sum, row) => {
    const status = row.status ?? "active";
    if (!ACTIVE_STATUSES.has(status) || Number(row.current_balance || 0) <= 0) return sum;
    return sum + Number(row.installment_amount || 0) * MONTHLY_FACTORS[row.installment_frequency || "monthly"];
  }, 0);
}

function setDebtField<K extends keyof CompanyClientExternalDebtInput>(
  debts: CompanyClientExternalDebtInput[],
  index: number,
  key: K,
  value: CompanyClientExternalDebtInput[K],
) {
  return debts.map((row, rowIndex) => {
    if (rowIndex !== index) return row;
    const next = { ...row, [key]: value };
    if ((key === "total_installments" || key === "installments_paid") && next.total_installments !== null && next.total_installments !== undefined) {
      next.remaining_installments = Math.max(Number(next.total_installments) - Number(next.installments_paid || 0), 0);
    }
    return next;
  });
}

function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return <div className={`space-y-1.5 ${className}`}><Label>{label}</Label>{children}</div>;
}

export function ExternalDebtRegistrationFields({
  debts,
  onChange,
  disabled = false,
}: {
  debts: CompanyClientExternalDebtInput[];
  onChange: (debts: CompanyClientExternalDebtInput[]) => void;
  disabled?: boolean;
}) {
  const balance = activeExternalDebtBalance(debts);
  const monthly = monthlyExternalDebtCommitment(debts);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-2xl border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-black">External loan tracker</p>
          <p className="text-xs leading-5 text-muted-foreground">Record every loan separately so its start date, balance, installment and remaining schedule are available next time.</p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled={disabled} onClick={() => onChange([...debts, blankExternalDebt()])}><Plus className="h-4 w-4" />Add existing loan</Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border bg-background p-3"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Tracked loans</p><p className="mt-1 text-lg font-black">{debts.length}</p></div>
        <div className="rounded-xl border bg-background p-3"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">External balance</p><p className="mt-1 text-lg font-black">{formatMoney(balance)}</p></div>
        <div className="rounded-xl border bg-background p-3"><p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Monthly commitment</p><p className="mt-1 text-lg font-black">{formatMoney(monthly)}</p></div>
      </div>

      {debts.length === 0 ? (
        <Alert><AlertTitle>No external loan declared</AlertTitle><AlertDescription>Leave this section empty only after the borrower confirms they have no loan outside LoanHub.</AlertDescription></Alert>
      ) : (
        <div className="space-y-4">
          {debts.map((debt, index) => (
            <Card key={`${index}-${debt.account_reference ?? "debt"}`} className="rounded-2xl shadow-none">
              <CardHeader className="flex-row items-center justify-between gap-3 border-b py-4">
                <div><CardTitle className="text-sm">Existing loan {index + 1}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{debt.creditor || "Lender not entered"} · {formatMoney(Number(debt.current_balance || 0))} outstanding</p></div>
                <div className="flex items-center gap-2"><Badge variant="outline">{titleCase(debt.status ?? "active")}</Badge><Button type="button" size="icon" variant="ghost" disabled={disabled} aria-label={`Remove existing loan ${index + 1}`} onClick={() => onChange(debts.filter((_, rowIndex) => rowIndex !== index))}><Trash2 className="h-4 w-4 text-destructive" /></Button></div>
              </CardHeader>
              <CardContent className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Lender or creditor"><Input disabled={disabled} value={debt.creditor} onChange={(event) => onChange(setDebtField(debts, index, "creditor", event.target.value))} /></Field>
                <Field label="Account reference"><Input disabled={disabled} value={debt.account_reference ?? ""} onChange={(event) => onChange(setDebtField(debts, index, "account_reference", event.target.value))} /></Field>
                <Field label="Loan started"><Input disabled={disabled} type="date" max={today} value={debt.started_on ?? ""} onChange={(event) => onChange(setDebtField(debts, index, "started_on", event.target.value || null))} /></Field>
                <Field label="Debt type"><Input disabled={disabled} value={debt.debt_type ?? ""} placeholder="Personal loan, store account..." onChange={(event) => onChange(setDebtField(debts, index, "debt_type", event.target.value))} /></Field>
                <Field label="Original amount"><Input disabled={disabled} type="number" min="0" step="0.01" value={debt.original_amount} onChange={(event) => onChange(setDebtField(debts, index, "original_amount", Number(event.target.value || 0)))} /></Field>
                <Field label="Current balance"><Input disabled={disabled} type="number" min="0" step="0.01" value={debt.current_balance} onChange={(event) => onChange(setDebtField(debts, index, "current_balance", Number(event.target.value || 0)))} /></Field>
                <Field label="Installment amount"><Input disabled={disabled} type="number" min="0" step="0.01" value={debt.installment_amount} onChange={(event) => onChange(setDebtField(debts, index, "installment_amount", Number(event.target.value || 0)))} /></Field>
                <Field label="Frequency"><Select disabled={disabled} value={debt.installment_frequency} onValueChange={(value) => onChange(setDebtField(debts, index, "installment_frequency", value as ExternalDebtFrequency))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{(["weekly", "fortnightly", "monthly", "quarterly", "custom"] as ExternalDebtFrequency[]).map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select></Field>
                <Field label="Total installments"><Input disabled={disabled} type="number" min="0" step="1" value={debt.total_installments ?? ""} onChange={(event) => onChange(setDebtField(debts, index, "total_installments", event.target.value === "" ? null : Number(event.target.value)))} /></Field>
                <Field label="Installments paid"><Input disabled={disabled} type="number" min="0" step="1" value={debt.installments_paid ?? 0} onChange={(event) => onChange(setDebtField(debts, index, "installments_paid", Number(event.target.value || 0)))} /></Field>
                <Field label="Installments remaining"><Input disabled={disabled} type="number" min="0" step="1" value={debt.remaining_installments ?? ""} onChange={(event) => onChange(setDebtField(debts, index, "remaining_installments", event.target.value === "" ? null : Number(event.target.value)))} /></Field>
                <Field label="Next due date"><Input disabled={disabled} type="date" value={debt.next_due_date ?? ""} onChange={(event) => onChange(setDebtField(debts, index, "next_due_date", event.target.value || null))} /></Field>
                <Field label="Status"><Select disabled={disabled} value={debt.status ?? "active"} onValueChange={(value) => onChange(setDebtField(debts, index, "status", value as ExternalDebtStatus))}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{(["active", "restructured", "defaulted", "settled", "written_off", "unknown"] as ExternalDebtStatus[]).map((value) => <SelectItem key={value} value={value}>{titleCase(value)}</SelectItem>)}</SelectContent></Select></Field>
                <label className="flex items-center gap-3 rounded-xl border p-3 lg:mt-6"><Checkbox disabled={disabled} checked={debt.is_verified === true} onCheckedChange={(checked) => onChange(setDebtField(debts, index, "is_verified", checked === true))} /><span className="text-sm font-bold">Evidence verified</span></label>
                <Field label="Notes" className="sm:col-span-2 lg:col-span-2"><Textarea disabled={disabled} rows={2} value={debt.notes ?? ""} onChange={(event) => onChange(setDebtField(debts, index, "notes", event.target.value))} /></Field>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
