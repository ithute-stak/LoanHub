"use client";

import { useEffect, useState } from "react";
import { originationApi } from "@/api/origination";
import type { Loan } from "@/types/loan";
import type { TopUpEligibility } from "@/types/origination";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatMoney } from "@/lib/format";
import { toast } from "@/utils/toast";
import { getErrorMessage } from "@/utils/apiError";

type Props = {
  loan: Loan | null;
  onClose: () => void;
  onCreated: (applicationId: string) => void;
};

function inheritedDates(loan: Loan): string[] {
  const term = Math.max(1, Math.min(120, Math.trunc(loan.repayment_period || 1)));
  const day = loan.first_payment_due ? Number(loan.first_payment_due.slice(8, 10)) : 20;
  const now = new Date();
  const today = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
  const dates: string[] = [];
  let offset = 0;
  while (dates.length < term && offset < term + 24) {
    const monthStart = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() + offset, 1));
    const lastDay = new Date(Date.UTC(monthStart.getUTCFullYear(), monthStart.getUTCMonth() + 1, 0)).getUTCDate();
    const due = new Date(Date.UTC(monthStart.getUTCFullYear(), monthStart.getUTCMonth(), Math.min(day, lastDay)));
    if (due > today) dates.push(due.toISOString().slice(0, 10));
    offset++;
  }
  return dates;
}

export function CompactTopUpDialog({ loan, onClose, onCreated }: Props) {
  const [cash, setCash] = useState("");
  const [exceptionReason, setExceptionReason] = useState("");
  const [eligibility, setEligibility] = useState<TopUpEligibility | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setCash("");
    setExceptionReason("");
    setEligibility(null);
    if (!loan) return;
    let active = true;
    setLoading(true);
    originationApi.topUpEligibility(loan.borrower_id, loan.id)
      .then((data) => { if (active) setEligibility(data); })
      .catch((error: unknown) => {
        if (active) toast.error(getErrorMessage(error, "Could not check top-up eligibility"));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [loan]);

  if (!loan) return null;
  const amount = Number(cash);
  const validAmount = cash.trim() !== "" && Number.isFinite(amount) && amount > 0 && Math.abs(Math.round(amount * 100) - amount * 100) < 1e-7;
  const balance = eligibility?.loan?.balance ?? loan.balance;
  const ownerException = Boolean(eligibility?.requires_owner_exception && !eligibility?.eligible);
  const canCreate = Boolean((eligibility?.eligible || (ownerException && exceptionReason.trim().length >= 10)) && eligibility?.loan?.id === loan.id && validAmount && !loading && !saving);
  const dueDates = inheritedDates(loan);

  async function create() {
    if (!canCreate || !loan || !eligibility) return;
    setSaving(true);
    try {
      const created = await originationApi.createCompactTopUp({
        borrower_id: loan.borrower_id,
        branch_id: loan.branch_id,
        application_type: "top_up",
        parent_loan_id: loan.id,
        requested_amount: Number((balance + amount).toFixed(2)),
        top_up_cash_requested: amount,
        top_up_exception_reason: ownerException ? exceptionReason.trim() : null,
        term_count: dueDates.length,
        installment_due_dates: dueDates,
        purpose: "Loan top-up on existing loan " + loan.loan_reference,
      });
      toast.success("Top-up application created", {
        description: ownerException ? "Owner exception requested. The company owner must approve the exception and all credit checks must pass." : "Existing borrower details inherited. Assessment and approval are still required.",
      });
      onCreated(created.id);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Could not create the top-up"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <CustomDialog open={Boolean(loan)} onOpenChange={(open) => { if (!open && !saving) onClose(); }}>
      <div className="space-y-5 p-5">
        <div>
          <h2 className="text-xl font-bold">Top up existing loan</h2>
          <p className="text-sm text-muted-foreground">Loan {loan.loan_reference} — customer and repayment settings inherited.</p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-xl border p-3"><p className="text-muted-foreground">Current balance</p><strong>{formatMoney(balance)}</strong></div>
          <div className="rounded-xl border p-3"><p className="text-muted-foreground">Inherited period</p><strong>{dueDates.length} months</strong></div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="compact-top-up-cash">Additional cash to borrower (LSL)</Label>
          <Input id="compact-top-up-cash" type="number" min="0.01" step="0.01"
            value={cash} onChange={(event) => setCash(event.target.value)} placeholder="Enter top-up amount" />
        </div>
        <p className="text-sm">Proposed replacement principal: <strong>{formatMoney(balance + (validAmount ? amount : 0))}</strong></p>
        {loading ? <p className="text-sm text-muted-foreground">Checking eligibility...</p> : ownerException ? (
          <div className="space-y-2 rounded-xl border border-amber-300 bg-amber-50 p-3 text-amber-950">
            <p role="status" className="text-sm">Normal eligibility threshold not met: {eligibility?.reason}. An owner exception can be requested, subject to company policy.</p>
            <Label htmlFor="compact-top-up-exception">Reason for owner exception (at least 10 characters)</Label>
            <Textarea id="compact-top-up-exception" value={exceptionReason} onChange={(event) => setExceptionReason(event.target.value)} placeholder="Explain why this top-up should be reviewed" />
            <p className="text-xs">Requesting an exception does not approve the loan. Only a company owner can approve the exception.</p>
          </div>
        ) : eligibility && !eligibility.eligible ? (
          <p role="alert" className="text-sm text-destructive">Top-up unavailable: {eligibility.reason}</p>
        ) : null}
        <p className="text-xs text-muted-foreground">Submitting creates an application, not an approved loan. LoanHub must still validate current affordability, policy, contract and approval requirements before funds can be released.</p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={() => void create()} disabled={!canCreate}>{saving ? "Submitting..." : ownerException ? "Request owner exception" : "Submit top-up"}</Button>
        </div>
      </div>
    </CustomDialog>
  );
}
