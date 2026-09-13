"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarClock, CircleDollarSign, History, ShieldCheck } from "lucide-react";

import {
  createEarlySettlementQuote,
  payEarlySettlement,
} from "@/api/loans";
import {
  EMPTY_PAYMENT_EVIDENCE,
  PaymentMethodFields,
  type PaymentEvidence,
} from "@/components/payments/payment-method-fields";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Textarea } from "@/components/ui/textarea";
import { createIdempotencyKey, formatDate, formatMoney, titleCase } from "@/lib/format";
import { interestMethodLabel } from "@/lib/interest-methods";
import type { PaymentMethodOption } from "@/types/expenseManagement";
import type { EarlySettlement, Loan } from "@/types/loan";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type Props = {
  open: boolean;
  loan: Loan | null;
  methods: PaymentMethodOption[];
  onOpenChange: (open: boolean) => void;
  onCompleted: (loanId: string) => Promise<void> | void;
};

function localDateValue(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10);
}

function legacySettlementStartDate(loan: Loan | null): string {
  if (!loan) return localDateValue();
  return (
    loan.disbursed_at?.slice(0, 10)
    || loan.approved_at?.slice(0, 10)
    || localDateValue()
  );
}

function Stat({
  label,
  value,
  emphasis = false,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className="rounded-2xl border bg-muted/20 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={emphasis ? "mt-1 text-xl font-black text-primary" : "mt-1 text-lg font-black"}>
        {value}
      </p>
    </div>
  );
}

export function EarlySettlementDialog({
  open,
  loan,
  methods,
  onOpenChange,
  onCompleted,
}: Props) {
  const [settlementDate, setSettlementDate] = useState(localDateValue);
  const [quote, setQuote] = useState<EarlySettlement | null>(null);
  const [quoting, setQuoting] = useState(false);
  const [paying, setPaying] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [agreementNote, setAgreementNote] = useState("");
  const [agreementReference, setAgreementReference] = useState("");
  const [evidence, setEvidence] = useState<PaymentEvidence>(EMPTY_PAYMENT_EVIDENCE);
  const [idempotencyKey, setIdempotencyKey] = useState("");

  const isLegacyCashout = Boolean(
    loan
    && (
      loan.origination_channel === "legacy_cashout"
      || loan.calculation_breakdown?.source === "legacy_cashout_book"
    )
  );
  const today = localDateValue();
  const minimumSettlementDate = isLegacyCashout ? legacySettlementStartDate(loan) : today;
  const isHistoricalLegacySettlement = Boolean(
    isLegacyCashout && settlementDate && settlementDate < today
  );

  const settlementMethods = useMemo(
    () => methods.filter((item) => item.value === "cash" || item.value === "lelefapaygate"),
    [methods],
  );

  useEffect(() => {
    if (!open) return;
    setSettlementDate(localDateValue());
    setQuote(null);
    setAcknowledged(false);
    setAgreementNote("");
    setAgreementReference("");
    setEvidence(EMPTY_PAYMENT_EVIDENCE);
    setIdempotencyKey("");
  }, [open, loan?.id]);

  async function calculateQuote() {
    if (!loan || !settlementDate) return;
    setQuoting(true);
    try {
      const result = await createEarlySettlementQuote(loan.id, {
        settlement_date: settlementDate,
        valid_for_days: 3,
      });
      setQuote(result);
      setIdempotencyKey(createIdempotencyKey(`early-settlement-${loan.id}-${result.id}`));
      toast.success(
        isHistoricalLegacySettlement ? "Historical settlement quote calculated" : "Settlement quote calculated",
        {
          description: `${formatMoney(result.unearned_interest_rebate)} of unearned interest will be removed.`,
        },
      );
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The settlement quote could not be calculated."));
    } finally {
      setQuoting(false);
    }
  }

  async function settle() {
    if (!loan || !quote) return;
    if (!acknowledged) {
      toast.warning("Confirm the borrower's settlement acknowledgement.");
      return;
    }
    if (agreementNote.trim().length < 3) {
      toast.warning("Record the settlement agreement or acknowledgement.");
      return;
    }

    const paymentMethod = isHistoricalLegacySettlement ? "cash" : evidence.payment_method;
    if (
      paymentMethod === "lelefapaygate"
      && (!evidence.gateway_provider || !evidence.gateway_customer_phone.trim())
    ) {
      toast.warning("Choose a LelefaPayGate provider and enter the required customer phone number.");
      return;
    }

    setPaying(true);
    try {
      const result = await payEarlySettlement(loan.id, quote.id, {
        payment_method: paymentMethod,
        gateway_provider: paymentMethod === "lelefapaygate" ? evidence.gateway_provider || null : null,
        gateway_customer_phone: paymentMethod === "lelefapaygate" ? evidence.gateway_customer_phone.trim() || null : null,
        borrower_acknowledged: acknowledged,
        agreement_note: agreementNote.trim(),
        agreement_reference: agreementReference.trim() || null,
        notes: evidence.proof_notes.trim() || null,
        idempotency_key: idempotencyKey,
      });
      setQuote(result.settlement);
      if (result.payment.status === "succeeded") {
        toast.success(isHistoricalLegacySettlement ? "Historical settlement recorded" : "Loan settled early", {
          description: `${loan.loan_reference} now has a ${result.settlement.chargeable_periods}-month charge and ${formatMoney(result.settlement.unearned_interest_rebate)} interest rebate.`,
        });
        await onCompleted(loan.id);
        onOpenChange(false);
      } else {
        toast.success("Settlement payment sent to LelefaPayGate", {
          description: `Status: ${titleCase(result.payment.status)}. The agreement changes only after confirmed success.`,
        });
      }
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The early settlement could not be completed."));
    } finally {
      setPaying(false);
    }
  }

  return (
    <CustomDialog
      open={open}
      onOpenChange={(next) => {
        if (!paying) onOpenChange(next);
      }}
      title="Settle loan early"
      description={
        loan
          ? `${loan.loan_reference} · Recalculate earned interest with the original loan method.`
          : undefined
      }
      contentClassName="sm:max-w-3xl"
    >
      <div className="space-y-5 p-5 sm:p-7">
        {loan ? (
          <>
            <Alert>
              <ShieldCheck className="h-4 w-4" />
              <AlertTitle>Controlled settlement addendum</AlertTitle>
              <AlertDescription>
                Advance payments keep the original agreement. Early settlement shortens the
                chargeable term, rebates future interest, preserves the signed contract and
                original schedule for audit, and applies only after Cash or LelefaPayGate success.
              </AlertDescription>
            </Alert>

            {isHistoricalLegacySettlement ? (
              <Alert className="border-amber-500/30 bg-amber-500/5">
                <History className="h-4 w-4 text-amber-700" />
                <AlertTitle>Historical legacy settlement</AlertTitle>
                <AlertDescription>
                  This date is before today and belongs to a migrated cash-out book. LoanHub will
                  record the settlement as Cash using {formatDate(settlementDate)} as the effective
                  payment and settlement date, while preserving the current audit-recording time.
                  Only the Company Owner can post this backdated settlement.
                </AlertDescription>
              </Alert>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
              <div className="space-y-2">
                <Label htmlFor="settlement-date">Interest charge-through / settlement date</Label>
                <Input
                  id="settlement-date"
                  type="date"
                  min={minimumSettlementDate}
                  value={settlementDate}
                  disabled={quoting || paying}
                  onChange={(event) => {
                    setSettlementDate(event.target.value);
                    setQuote(null);
                  }}
                />
                <p className="text-xs leading-5 text-muted-foreground">
                  {isLegacyCashout
                    ? "Legacy cash-out loans may use a past settlement date from the original book."
                    : "Live LoanHub loans cannot be settled using a date before today."}
                </p>
              </div>
              <LoadingButton
                loading={quoting}
                loadingText="Calculating…"
                disabled={!settlementDate || paying}
                onClick={() => void calculateQuote()}
              >
                <CalendarClock className="h-4 w-4" />
                Calculate secure quote
              </LoadingButton>
            </div>

            {quote ? (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{interestMethodLabel(quote.calculation_method)}</Badge>
                  <Badge variant="secondary">
                    {quote.original_term_months} months → {quote.chargeable_periods} months
                  </Badge>
                  <Badge variant="outline">Valid until {formatDate(quote.quote_expires_at)}</Badge>
                  {isHistoricalLegacySettlement ? (
                    <Badge variant="outline" className="border-amber-500/30 text-amber-700">
                      Historical · Cash only
                    </Badge>
                  ) : null}
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Stat label="Original interest" value={formatMoney(quote.original_total_interest)} />
                  <Stat label="Earned interest" value={formatMoney(quote.earned_interest)} />
                  <Stat
                    label="Interest rebate"
                    value={formatMoney(quote.unearned_interest_rebate)}
                    emphasis
                  />
                  <Stat
                    label="Settlement due"
                    value={formatMoney(quote.settlement_amount)}
                    emphasis
                  />
                </div>

                <div className="rounded-2xl border p-4 text-sm">
                  <div className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Payments already received</span>
                    <strong>{formatMoney(quote.payments_received)}</strong>
                  </div>
                  <div className="mt-2 flex justify-between gap-4">
                    <span className="text-muted-foreground">Processing fee retained</span>
                    <strong>{formatMoney(quote.processing_fee_retained)}</strong>
                  </div>
                  <div className="mt-2 flex justify-between gap-4 border-t pt-2">
                    <span className="text-muted-foreground">Revised agreement total</span>
                    <strong>{formatMoney(quote.revised_total_repayable)}</strong>
                  </div>
                </div>

                {isHistoricalLegacySettlement ? (
                  <div className="rounded-2xl border border-amber-500/25 bg-amber-500/5 p-4 text-sm">
                    <p className="font-black">Historical payment method: Cash</p>
                    <p className="mt-1 leading-5 text-muted-foreground">
                      Electronic gateway settlement is disabled for a past book entry. The final
                      settlement payment will carry the historical effective date above.
                    </p>
                  </div>
                ) : (
                  <PaymentMethodFields
                    methods={settlementMethods}
                    value={evidence}
                    onChange={setEvidence}
                    disabled={paying}
                  />
                )}

                <div className="space-y-2">
                  <Label htmlFor="settlement-agreement">Settlement agreement / acknowledgement</Label>
                  <Textarea
                    id="settlement-agreement"
                    value={agreementNote}
                    disabled={paying}
                    placeholder={
                      isHistoricalLegacySettlement
                        ? "Example: Original cash-out book confirms the borrower settled this account in full on the selected historical date."
                        : "Example: Borrower reviewed the revised one-month charge and settlement amount and agreed to settle the account in full."
                    }
                    onChange={(event) => setAgreementNote(event.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="settlement-reference">
                    {isHistoricalLegacySettlement ? "Original book / settlement reference (optional)" : "Signed addendum reference (optional)"}
                  </Label>
                  <Input
                    id="settlement-reference"
                    value={agreementReference}
                    disabled={paying}
                    placeholder={isHistoricalLegacySettlement ? "BOOK-01 / FOLIO-00124" : "ADD-2026-001"}
                    onChange={(event) => setAgreementReference(event.target.value)}
                  />
                </div>

                <label className="flex cursor-pointer items-start gap-3 rounded-2xl border p-4 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4"
                    checked={acknowledged}
                    disabled={paying}
                    onChange={(event) => setAcknowledged(event.target.checked)}
                  />
                  <span>
                    <strong className="block">
                      {isHistoricalLegacySettlement ? "Historical settlement evidence confirmed" : "Borrower acknowledgement recorded"}
                    </strong>
                    {isHistoricalLegacySettlement
                      ? "I confirm the original book or supporting record shows this account was settled on the selected historical date."
                      : "The borrower understands the revised term, retained fee, earned interest, interest rebate and final settlement amount."}
                  </span>
                </label>
              </>
            ) : null}
          </>
        ) : null}

        <DialogFooter className="mx-0 mb-0 flex-wrap">
          <Button variant="outline" disabled={paying} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {quote ? (
            <LoadingButton
              loading={paying}
              loadingText={isHistoricalLegacySettlement ? "Recording historical settlement…" : "Securing settlement…"}
              disabled={!acknowledged || agreementNote.trim().length < 3 || quote.settlement_amount <= 0}
              onClick={() => void settle()}
            >
              <CircleDollarSign className="h-4 w-4" />
              {isHistoricalLegacySettlement ? "Record" : "Settle"} {formatMoney(quote.settlement_amount)}
            </LoadingButton>
          ) : null}
        </DialogFooter>
      </div>
    </CustomDialog>
  );
}
