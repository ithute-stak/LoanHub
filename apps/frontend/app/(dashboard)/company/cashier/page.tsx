"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  ArrowDownLeft,
  Calculator,
  CalendarClock,
  CheckCircle2,
  CircleAlert,
  Coins,
  CreditCard,
  Download,
  PenLine,
  Printer,
  ReceiptText,
  Search,
  Undo2,
} from "lucide-react";

import { listCompanyClients } from "@/api/companyClients";
import { expenseManagementApi } from "@/api/expenseManagement";
import { adjustInstallmentDueDate, collectRepayment, getLoanByReference, listLoans, previewRepayment } from "@/api/loans";
import { downloadPaymentReceiptPdf, printPaymentReceiptPdf } from "@/api/paymentReceipts";
import { EarlySettlementDialog } from "@/components/loans/early-settlement-dialog";
import {
  DEFAULT_PAYMENT_METHOD_OPTIONS,
  EMPTY_PAYMENT_EVIDENCE,
  PaymentMethodFields,
  type PaymentEvidence,
} from "@/components/payments/payment-method-fields";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { SuggestionSearch, fuzzySearchScore } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { createIdempotencyKey, formatDate, formatMoney, titleCase } from "@/lib/format";
import { interestMethodLabel } from "@/lib/interest-methods";
import { useTenant } from "@/provider/tenantProvider";
import { FINANCE_ROLES, LENDING_ROLES, hasRole } from "@/types/auth";
import type { CompanyClient } from "@/types/companyClient";
import type { PaymentMethodOption } from "@/types/expenseManagement";
import type { CashPaymentResult, CashRepaymentPreview, Loan, OverpaymentAction, RepaymentInstallment } from "@/types/loan";
import { toast } from "@/utils/toast";

function dayAfterIsoDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day + 1));
  return next.toISOString().slice(0, 10);
}

function dayBeforeIsoDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  const previous = new Date(Date.UTC(year, month - 1, day - 1));
  return previous.toISOString().slice(0, 10);
}

function localTodayIsoDate(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export default function CompanyCashierPage() {
  const { activeRole } = useTenant();
  const canAdjustDueDates = hasRole(activeRole, LENDING_ROLES);
  const canSettleEarly = hasRole(activeRole, FINANCE_ROLES);
  const canBackdatePayments = activeRole === "company_owner";

  const [loanReference, setLoanReference] = useState("");
  const [loan, setLoan] = useState<Loan | null>(null);
  const [amount, setAmount] = useState("");
  const [paymentDate, setPaymentDate] = useState(localTodayIsoDate);
  const [action, setAction] = useState<OverpaymentAction>("carry_forward");
  const [evidence, setEvidence] = useState<PaymentEvidence>(EMPTY_PAYMENT_EVIDENCE);
  const [methods, setMethods] = useState<PaymentMethodOption[]>(DEFAULT_PAYMENT_METHOD_OPTIONS);
  const [loanDirectory, setLoanDirectory] = useState<Loan[]>([]);
  const [clientDirectory, setClientDirectory] = useState<CompanyClient[]>([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [paying, setPaying] = useState(false);
  const [preview, setPreview] = useState<CashRepaymentPreview | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [settlementOpen, setSettlementOpen] = useState(false);
  const [receipt, setReceipt] = useState<CashPaymentResult | null>(null);
  const [receiptAction, setReceiptAction] = useState<"download" | "print" | null>(null);
  const [editingInstallment, setEditingInstallment] = useState<RepaymentInstallment | null>(null);
  const [extendedDueDate, setExtendedDueDate] = useState("");
  const [extensionNote, setExtensionNote] = useState("");
  const [extensionReference, setExtensionReference] = useState("");
  const [extendingDueDate, setExtendingDueDate] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      const [methodRows, loanRows, clientRows] = await Promise.all([
        expenseManagementApi.paymentMethods().catch(() => DEFAULT_PAYMENT_METHOD_OPTIONS),
        listLoans().catch(() => []),
        listCompanyClients().catch(() => []),
      ]);

      if (cancelled) return;
      setMethods(methodRows);
      setLoanDirectory(loanRows);
      setClientDirectory(clientRows);

      const requestedLoan = new URLSearchParams(window.location.search).get("loan")?.trim();
      if (requestedLoan) setLoanReference(requestedLoan);
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  const clientByBorrower = useMemo(
    () => new Map(clientDirectory.map((client) => [client.borrower_id, client])),
    [clientDirectory],
  );

  const searchableLoans = useMemo(() => loanDirectory.map((candidate) => {
    const client = clientByBorrower.get(candidate.borrower_id);
    const searchText = [
      candidate.loan_reference,
      candidate.id,
      candidate.borrower_id,
      candidate.status,
      client?.full_name,
      client?.account_reference,
      client?.national_id,
      client?.passport_number,
      client?.phone,
      client?.email,
    ].filter(Boolean).join(" ");

    return { loan: candidate, client, searchText };
  }), [clientByBorrower, loanDirectory]);

  const rankedMatches = useMemo(() => {
    const query = loanReference.trim();
    if (!query) return [];

    return searchableLoans
      .map((item, index) => ({
        ...item,
        index,
        score: fuzzySearchScore(query, item.searchText),
      }))
      .filter((item) => Number.isFinite(item.score))
      .sort((left, right) => left.score - right.score || left.index - right.index);
  }, [loanReference, searchableLoans]);

  const loanSuggestions = useMemo(() => searchableLoans.map(({ loan: candidate, client }) => ({
    value: candidate.loan_reference,
    label: client?.full_name
      ? `${client.full_name} · ${candidate.loan_reference}`
      : candidate.loan_reference,
    description: [
      client?.account_reference,
      titleCase(candidate.status),
      formatMoney(candidate.balance),
    ].filter(Boolean).join(" · "),
    keywords: [
      candidate.id,
      candidate.borrower_id,
      client?.full_name ?? "",
      client?.account_reference ?? "",
      client?.national_id ?? "",
      client?.passport_number ?? "",
      client?.phone ?? "",
      client?.email ?? "",
    ],
  })), [searchableLoans]);

  const amountValue = Number(amount || 0);
  const isCash = evidence.payment_method === "cash";
  const methodLabel = methods.find((item) => item.value === evidence.payment_method)?.label ?? titleCase(evidence.payment_method);
  const selectedInstallment = useMemo(
    () => loan?.installments.find((item) => item.status !== "paid" && item.status !== "waived") ?? null,
    [loan],
  );
  const nextInstallmentForAdjustment = useMemo(() => {
    if (!loan || !editingInstallment) return null;

    return [...loan.installments]
      .filter((item) => item.installment_number > editingInstallment.installment_number)
      .sort((left, right) => left.installment_number - right.installment_number)[0] ?? null;
  }, [editingInstallment, loan]);
  const repaymentProgress = useMemo(() => {
    if (!loan || Number(loan.total_repayable) <= 0) return 0;
    return Math.min(100, Math.max(0, (Number(loan.amount_paid) / Number(loan.total_repayable)) * 100));
  }, [loan]);

  const resetPayment = useCallback(() => {
    setAmount("");
    setPaymentDate(localTodayIsoDate());
    setPreview(null);
    setAction("carry_forward");
    setEvidence(EMPTY_PAYMENT_EVIDENCE);
  }, []);

  const loadLoan = useCallback(async (reference: string, quiet = false) => {
    const exactReference = reference.trim();
    if (!exactReference) return;

    setLookupLoading(true);
    setPreview(null);
    setReceipt(null);
    try {
      const found = await getLoanByReference(exactReference);
      setLoan(found);
      setLoanReference(found.loan_reference);
      resetPayment();
    } catch (error) {
      setLoan(null);
      if (!quiet) {
        toast.error(error, { description: "No accessible loan matched this search." });
      }
    } finally {
      setLookupLoading(false);
    }
  }, [resetPayment]);

  async function lookup(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const query = loanReference.trim();
    if (!query) {
      toast.warning("Enter part of a loan number, borrower name, client number, ID or phone.");
      return;
    }

    const exactReference = searchableLoans.find(
      (item) => item.loan.loan_reference.toLocaleLowerCase() === query.toLocaleLowerCase(),
    );
    if (exactReference) {
      await loadLoan(exactReference.loan.loan_reference);
      return;
    }

    if (rankedMatches.length === 1) {
      await loadLoan(rankedMatches[0].loan.loan_reference);
      return;
    }

    if (rankedMatches.length > 1) {
      toast.info("Several loans match that text", {
        description: "Keep typing or choose one of the suggestions below the search field.",
      });
      return;
    }

    // Preserve direct exact-reference lookup when the local directory is unavailable/stale.
    await loadLoan(query);
  }

  useEffect(() => {
    const query = loanReference.trim();
    if (query.length < 3 || lookupLoading) return;
    if (loan?.loan_reference.toLocaleLowerCase() === query.toLocaleLowerCase()) return;
    if (rankedMatches.length !== 1) return;

    const candidate = rankedMatches[0];
    if (candidate.score > 4) return;

    const timer = window.setTimeout(() => {
      void loadLoan(candidate.loan.loan_reference, true);
    }, 350);

    return () => window.clearTimeout(timer);
  }, [loan, loanReference, loadLoan, lookupLoading, rankedMatches]);

  function updateEvidence(value: PaymentEvidence) {
    setEvidence(value);
    setPreview(null);
    if (value.payment_method !== "cash" && action === "give_change") {
      setAction("carry_forward");
    }
  }

  async function calculatePreview() {
    if (!loan || !Number.isFinite(amountValue) || amountValue <= 0) {
      toast.warning("Enter a positive payment amount.");
      return;
    }
    setPreviewLoading(true);
    try {
      const calculated = await previewRepayment({
        loan_reference: loan.loan_reference,
        amount_tendered: amountValue,
        overpayment_action: isCash ? action : "carry_forward",
        installment_number: selectedInstallment?.installment_number,
        payment_method: evidence.payment_method,
        payment_date: canBackdatePayments ? paymentDate : null,
      });
      setPreview(calculated);
      setConfirmOpen(true);
    } catch (error) {
      toast.error(error, { description: "The repayment preview could not be calculated." });
    } finally {
      setPreviewLoading(false);
    }
  }

  function openEarlySettlement() {
    if (!loan || !canSettleEarly) return;
    setConfirmOpen(false);
    setSettlementOpen(true);
  }

  async function collectPayment() {
    if (!loan || !preview) return;
    if (preview.early_settlement_required) {
      toast.warning("Use the early-settlement quote", {
        description: "This payoff includes future instalment interest and cannot be posted as an ordinary advance payment.",
      });
      return;
    }
    if (
      evidence.payment_method === "lelefapaygate"
      && (!evidence.gateway_provider || !evidence.gateway_customer_phone.trim())
    ) {
      toast.warning("Choose a LelefaPayGate provider and enter the required customer phone number.");
      return;
    }
    if (!isCash && evidence.payment_method !== "lelefapaygate" && !evidence.proof_reference.trim() && !evidence.proof_url.trim()) {
      toast.warning("Enter a proof reference or proof document location.");
      return;
    }
    setPaying(true);
    try {
      const result = await collectRepayment({
        loan_reference: loan.loan_reference,
        amount_tendered: amountValue,
        overpayment_action: isCash ? action : "carry_forward",
        installment_number: preview.current_installment_number,
        payment_method: evidence.payment_method,
        gateway_provider: evidence.gateway_provider || null,
        gateway_customer_phone: evidence.gateway_customer_phone.trim() || null,
        proof_reference: evidence.proof_reference.trim() || null,
        proof_url: evidence.proof_url.trim() || null,
        proof_notes: evidence.proof_notes.trim() || null,
        notes: evidence.proof_notes.trim() || undefined,
        idempotency_key: createIdempotencyKey(`repayment-${evidence.payment_method}-${loan.id}`),
        payment_date: canBackdatePayments ? paymentDate : null,
      });
      setReceipt(result);
      setConfirmOpen(false);
      setLoan(await getLoanByReference(loan.loan_reference));
      toast.success("Loan repayment recorded", {
        description: `${methodLabel} payment ${result.provider_reference} was posted to the loan, accounting and branch money register.`,
      });
      resetPayment();
    } catch (error) {
      toast.error(error, { description: "The repayment was not recorded." });
    } finally {
      setPaying(false);
    }
  }


  function openDueDateAdjustment(installment: RepaymentInstallment) {
    setEditingInstallment(installment);
    setExtendedDueDate(dayAfterIsoDate(installment.due_date));
    setExtensionNote("");
    setExtensionReference("");
  }

  function closeDueDateAdjustment() {
    if (extendingDueDate) return;
    setEditingInstallment(null);
  }

  async function saveDueDateAdjustment() {
    if (!loan || !editingInstallment) return;

    if (!extendedDueDate) {
      toast.warning("Choose the agreed new due date.");
      return;
    }

    if (extensionNote.trim().length < 3) {
      toast.warning("Record the agreement or reason for adjusting the due date.");
      return;
    }

    setExtendingDueDate(true);
    try {
      const updated = await adjustInstallmentDueDate(loan.id, editingInstallment.id, {
        new_due_date: extendedDueDate,
        agreement_note: extensionNote.trim(),
        agreement_reference: extensionReference.trim() || null,
      });

      setLoan(updated);
      setLoanDirectory((rows) => rows.map((item) => (item.id === updated.id ? updated : item)));
      setEditingInstallment(null);

      toast.success("Installment due date adjusted", {
        description: `Installment ${editingInstallment.installment_number} is now due ${formatDate(extendedDueDate)}.`,
      });
    } catch (error) {
      toast.error(error, {
        description: "The installment due date could not be adjusted.",
      });
    } finally {
      setExtendingDueDate(false);
    }
  }

  async function downloadReceipt() {
    if (!loan || !receipt) return;
    setReceiptAction("download");
    try {
      await downloadPaymentReceiptPdf({
        loanId: loan.id,
        paymentId: receipt.payment_id,
        receiptNumber: receipt.receipt_number ?? receipt.provider_reference,
      });
    } catch (error) {
      toast.error(error, {
        description: "The receipt PDF could not be downloaded. The repayment is still recorded.",
      });
    } finally {
      setReceiptAction(null);
    }
  }

  async function printReceipt() {
    if (!loan || !receipt) return;
    setReceiptAction("print");
    try {
      await printPaymentReceiptPdf({
        loanId: loan.id,
        paymentId: receipt.payment_id,
        receiptNumber: receipt.receipt_number ?? receipt.provider_reference,
        companyId: loan.company_id,
      });
    } catch (error) {
      toast.error(error, {
        description: "The receipt PDF could not be opened for printing. The repayment is still recorded.",
      });
    } finally {
      setReceiptAction(null);
    }
  }

  return (
    <div className="loanhub-page">
      <section className="loanhub-hero p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[1fr_420px] lg:items-end">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Payment desk</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Receive a loan instalment</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
              Verify the loan and borrower, identify how the money was received, capture proof for non-cash channels, preview partial or advance allocation, and issue a receipt.
            </p>
          </div>
          <StickyFilterBar
            ariaLabel="Cashier loan and borrower search"
            className="rounded-3xl data-[floating=true]:border"
          >
            <form onSubmit={lookup} className="rounded-[inherit] border bg-background/90 p-3 shadow-sm backdrop-blur">
              <Label htmlFor="loan-reference" className="sr-only">Loan or borrower search</Label>
              <div className="flex gap-2">
                <SuggestionSearch
                  id="loan-reference"
                  value={loanReference}
                  onValueChange={(value) => {
                    setLoanReference(value);
                    if (loan && value.trim().toLocaleLowerCase() !== loan.loan_reference.toLocaleLowerCase()) {
                      setLoan(null);
                      setPreview(null);
                    }
                  }}
                  suggestions={loanSuggestions}
                  minimumCharacters={1}
                  maxSuggestions={10}
                  placeholder="Type loan, borrower, client, ID or phone..."
                  suggestionLabel="Matching loans"
                  emptyMessage="No accessible loan matches this text."
                  wrapperClassName="min-w-0 flex-1"
                  className="font-mono"
                  onSuggestionSelect={(suggestion) => void loadLoan(suggestion.value)}
                />
                <LoadingButton type="submit" loading={lookupLoading} loadingText="Searching"><Search className="h-4 w-4" />Find</LoadingButton>
              </div>
              <p className="mt-2 px-1 text-xs text-muted-foreground">Search updates as you type. Partial fragments such as <span className="font-mono font-semibold">si-90</span> can match values such as <span className="font-mono font-semibold">Koetlisi-9088</span>.</p>
            </form>
          </StickyFilterBar>
        </div>
      </section>

      {!loan ? (
        <Card className="loanhub-panel">
          <CardContent className="flex min-h-72 flex-col items-center justify-center p-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-primary/10 text-primary"><ReceiptText className="h-8 w-8" /></div>
            <h2 className="mt-5 text-xl font-black">Search for the loan or borrower</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">Type any recognisable part of the loan number, borrower name, client number, national ID or phone. LoanHub suggests matches and opens a unique match automatically.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1.15fr_.85fr]">
          <div className="space-y-6">
            <Card className="loanhub-panel overflow-hidden">
              <CardHeader className="border-b bg-gradient-to-r from-primary/10 to-emerald-500/10">
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                  <div><p className="font-mono text-xs font-black text-primary">{loan.loan_reference}</p><CardTitle className="mt-2">Verified loan</CardTitle><CardDescription>{interestMethodLabel(loan.calculation_method)} · {loan.repayment_period} monthly instalments</CardDescription></div>
                  <Badge variant={loan.status === "active" ? "default" : "secondary"}>{titleCase(loan.status)}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-5 p-5 sm:p-6">
                <div className="grid gap-3 sm:grid-cols-4"><Value label="Principal" value={formatMoney(loan.principal_amount)} /><Value label="Total repayable" value={formatMoney(loan.total_repayable)} /><Value label="Paid" value={formatMoney(loan.amount_paid)} /><Value label="Outstanding" value={formatMoney(loan.balance)} emphasis /></div>
                <div><div className="mb-2 flex justify-between text-xs font-bold"><span>Loan repayment progress</span><span>{repaymentProgress.toFixed(1)}%</span></div><Progress value={repaymentProgress} className="h-2.5" /></div>
                {selectedInstallment ? <Alert><CircleAlert className="h-4 w-4" /><AlertTitle>Current instalment {selectedInstallment.installment_number}</AlertTitle><AlertDescription>Due {formatDate(selectedInstallment.due_date)} · Expected {formatMoney(selectedInstallment.total_due)} · Paid {formatMoney(selectedInstallment.paid_amount)} · Remaining {formatMoney(Number(selectedInstallment.total_due) - Number(selectedInstallment.paid_amount))}</AlertDescription></Alert> : <Alert><CheckCircle2 className="h-4 w-4" /><AlertTitle>No unpaid instalment</AlertTitle><AlertDescription>This loan has no outstanding scheduled instalment.</AlertDescription></Alert>}
              </CardContent>
            </Card>

            <Card className="loanhub-panel overflow-hidden">
              <CardHeader>
                <CardTitle>Repayment schedule</CardTitle>
                <CardDescription>
                  Payments are allocated to the oldest unpaid instalment first. Lending-authorised staff can also move an unpaid due date to a later agreed date.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>#</TableHead>
                        <TableHead>Due date</TableHead>
                        <TableHead>Expected</TableHead>
                        <TableHead>Paid</TableHead>
                        <TableHead>Remaining</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loan.installments.map((installment) => {
                        const lockedInstallment = ["paid", "waived"].includes(installment.status);
                        const editableLoan = ["approved", "active", "defaulted"].includes(loan.status);
                        const canAdjust = canAdjustDueDates && editableLoan && !lockedInstallment;

                        const actionTitle = lockedInstallment
                          ? "Paid or waived installments are locked"
                          : !editableLoan
                            ? `Dates cannot be adjusted while the loan is ${titleCase(loan.status)}`
                            : !canAdjustDueDates
                              ? "Your active role cannot adjust agreed installment dates"
                              : "Move this installment to a later agreed date";

                        return (
                          <TableRow key={installment.id}>
                            <TableCell className="font-black">{installment.installment_number}</TableCell>
                            <TableCell className="whitespace-nowrap">{formatDate(installment.due_date)}</TableCell>
                            <TableCell>{formatMoney(installment.total_due)}</TableCell>
                            <TableCell>{formatMoney(installment.paid_amount)}</TableCell>
                            <TableCell className="font-black">
                              {formatMoney(Math.max(0, Number(installment.total_due) - Number(installment.paid_amount)))}
                            </TableCell>
                            <TableCell>
                              <Badge variant={installment.status === "paid" ? "default" : "secondary"}>
                                {titleCase(installment.status)}
                              </Badge>
                            </TableCell>
                            <TableCell className="whitespace-nowrap text-right">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={!canAdjust}
                                title={actionTitle}
                                onClick={() => openDueDateAdjustment(installment)}
                              >
                                <PenLine className="h-3.5 w-3.5" />
                                Adjust date
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="loanhub-panel h-fit xl:sticky xl:top-24">
            <CardHeader><CardTitle className="flex items-center gap-2"><CreditCard className="h-5 w-5 text-primary" />Payment received</CardTitle><CardDescription>Select the actual channel. Non-cash methods are recorded only after staff verify the submitted proof.</CardDescription></CardHeader>
            <CardContent className="space-y-5">
              <PaymentMethodFields methods={methods} value={evidence} onChange={updateEvidence} />
              {canBackdatePayments ? (
                <div className="space-y-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
                  <Label htmlFor="payment-date">Payment date</Label>
                  <Input
                    id="payment-date"
                    type="date"
                    max={localTodayIsoDate()}
                    value={paymentDate}
                    onChange={(event) => { setPaymentDate(event.target.value); setPreview(null); }}
                  />
                  <p className="text-xs text-muted-foreground">Company Owner control: choose the actual historical payment date for legacy records. Future dates are never allowed.</p>
                </div>
              ) : null}
              <div className="space-y-2"><Label htmlFor="amount">Amount received</Label><Input id="amount" type="number" min="0.01" step="0.01" value={amount} onChange={(event) => { setAmount(event.target.value); setPreview(null); }} placeholder="0.00" className="h-14 text-2xl font-black" /></div>
              <div className="space-y-2"><Label>When payment exceeds the current instalment</Label><Select value={isCash ? action : "carry_forward"} disabled={!isCash} onValueChange={(value) => { setAction(value as OverpaymentAction); setPreview(null); }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="carry_forward">Keep excess as forward payment</SelectItem><SelectItem value="give_change">Apply current instalment and give cash change</SelectItem></SelectContent></Select>{!isCash ? <p className="text-xs text-muted-foreground">Non-cash overpayments are carried forward; the system cannot issue electronic change.</p> : null}</div>
              <LoadingButton className="h-12 w-full" loading={previewLoading} loadingText="Calculating..." onClick={() => void calculatePreview()} disabled={!selectedInstallment}><Calculator className="h-4 w-4" />Preview allocation</LoadingButton>
              <Button
                type="button"
                variant="outline"
                className="h-12 w-full"
                disabled={!canSettleEarly || !selectedInstallment}
                title={canSettleEarly ? "Recalculate earned interest and close this loan" : "A finance role must approve an early settlement"}
                onClick={openEarlySettlement}
              >
                <CalendarClock className="h-4 w-4" />
                Settle loan early
              </Button>
              {!canSettleEarly ? (
                <p className="text-xs text-muted-foreground">
                  A finance officer, treasury officer, company admin or company owner must approve a settlement that changes the agreement.
                </p>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}

      <EarlySettlementDialog
        open={settlementOpen}
        loan={loan}
        methods={methods}
        onOpenChange={setSettlementOpen}
        onCompleted={async () => {
          if (!loan) return;
          const updated = await getLoanByReference(loan.loan_reference);
          setLoan(updated);
          setConfirmOpen(false);
          resetPayment();
        }}
      />

      <CustomDialog
        open={Boolean(editingInstallment)}
        onOpenChange={(open) => {
          if (!open) closeDueDateAdjustment();
        }}
        title="Adjust installment due date"
        description={
          editingInstallment && loan
            ? `${loan.loan_reference} · Installment ${editingInstallment.installment_number}`
            : undefined
        }
        contentClassName="sm:max-w-xl"
      >
        <div className="space-y-5 p-5 sm:p-7">
          {editingInstallment ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <Value label="Current due date" value={formatDate(editingInstallment.due_date)} />
                <Value label="Installment total" value={formatMoney(editingInstallment.total_due)} />
                <Value label="Already paid" value={formatMoney(editingInstallment.paid_amount)} />
                <Value
                  label="Remaining"
                  value={formatMoney(Math.max(0, Number(editingInstallment.total_due) - Number(editingInstallment.paid_amount)))}
                  emphasis
                />
              </div>

              <Alert>
                <CalendarClock className="h-4 w-4" />
                <AlertTitle>Agreed due-date adjustment</AlertTitle>
                <AlertDescription>
                  Move the installment to a later agreed date only. Principal, interest, fees and the installment amount do not change.
                  {nextInstallmentForAdjustment
                    ? ` The new date must remain before installment ${nextInstallmentForAdjustment.installment_number}, due ${formatDate(nextInstallmentForAdjustment.due_date)}.`
                    : " This is the final installment, so the new date also becomes the loan maturity date."}
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <Label htmlFor="cashier-adjusted-due-date">Agreed new due date</Label>
                <Input
                  id="cashier-adjusted-due-date"
                  type="date"
                  value={extendedDueDate}
                  min={dayAfterIsoDate(editingInstallment.due_date)}
                  max={nextInstallmentForAdjustment ? dayBeforeIsoDate(nextInstallmentForAdjustment.due_date) : undefined}
                  onChange={(event) => setExtendedDueDate(event.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="cashier-adjustment-reason">Agreement / reason</Label>
                <Textarea
                  id="cashier-adjustment-reason"
                  value={extensionNote}
                  onChange={(event) => setExtensionNote(event.target.value)}
                  placeholder="Example: Borrower requested an extension and the lender approved the revised payment date."
                  rows={4}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="cashier-adjustment-reference">Agreement reference (optional)</Label>
                <Input
                  id="cashier-adjustment-reference"
                  value={extensionReference}
                  onChange={(event) => setExtensionReference(event.target.value)}
                  placeholder="Approval, meeting note, collection activity or document reference"
                />
              </div>
            </>
          ) : null}

          <DialogFooter className="mx-0 mb-0">
            <Button variant="outline" disabled={extendingDueDate} onClick={closeDueDateAdjustment}>
              Cancel
            </Button>
            <LoadingButton
              loading={extendingDueDate}
              loadingText="Saving date..."
              disabled={!extendedDueDate || extensionNote.trim().length < 3}
              onClick={() => void saveDueDateAdjustment()}
            >
              <CalendarClock className="h-4 w-4" />
              Save adjusted date
            </LoadingButton>
          </DialogFooter>
        </div>
      </CustomDialog>

      <CustomDialog open={confirmOpen} onOpenChange={(open) => !paying && setConfirmOpen(open)} title={`Confirm ${methodLabel} allocation`} description="Read the values back to the borrower before posting. This creates the receipt, repayment allocations, accounting entry and branch money movement." contentClassName="sm:max-w-2xl">
        <div className="space-y-5 p-6 sm:p-8">
          {preview ? <div className="space-y-4"><div className="rounded-3xl border bg-gradient-to-br from-primary/8 to-emerald-500/8 p-5"><div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/12 text-primary"><Coins className="h-6 w-6" /></div><p className="text-xs font-black uppercase tracking-[0.18em] text-muted-foreground">{preview.borrower_name}</p><p className="mt-1 font-mono text-sm font-black text-primary">{preview.loan_reference}</p><div className="mt-5 grid gap-3 sm:grid-cols-3"><Value label={`${methodLabel} received`} value={formatMoney(preview.amount_tendered)} emphasis /><Value label="Applied to loan" value={formatMoney(preview.amount_applied)} emphasis /><Value label="Loan after payment" value={formatMoney(preview.loan_balance_after)} /><Value label="Current instalment left" value={formatMoney(preview.installment_outstanding_after)} /><Value label="Forward balance" value={formatMoney(preview.forward_amount)} /><Value label="Change to give" value={formatMoney(preview.change_amount)} /></div></div>{preview.amount_tendered < preview.installment_outstanding_before ? <Alert variant="destructive"><CircleAlert className="h-4 w-4" /><AlertTitle>Partial instalment</AlertTitle><AlertDescription>{formatMoney(preview.installment_outstanding_after)} will remain due for instalment {preview.current_installment_number}.</AlertDescription></Alert> : null}{preview.change_amount > 0 ? <Alert><Undo2 className="h-4 w-4" /><AlertTitle>Give cash change</AlertTitle><AlertDescription>Return {formatMoney(preview.change_amount)} to the borrower. Only {formatMoney(preview.amount_applied)} is posted.</AlertDescription></Alert> : null}{preview.forward_amount > 0 ? <Alert><ArrowDownLeft className="h-4 w-4" /><AlertTitle>Advance payment</AlertTitle><AlertDescription>{formatMoney(preview.forward_amount)} is carried forward. {preview.installments_fully_covered} instalment(s) are fully covered.</AlertDescription></Alert> : null}{preview.early_settlement_required ? <Alert variant="destructive"><CircleAlert className="h-4 w-4" /><AlertTitle>Early-settlement quote required</AlertTitle><AlertDescription>This amount would close {preview.future_installments_in_payoff} future instalment(s) using the old full-term interest. LoanHub will not post it as an ordinary payment. Use the settlement quote to remove unearned interest and record the revised agreement.</AlertDescription></Alert> : null}</div> : null}
          <DialogFooter className="mx-0 mb-0 flex-wrap">
            <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={paying}>Review again</Button>
            {preview?.early_settlement_required ? (
              canSettleEarly ? (
                <Button onClick={openEarlySettlement}>
                  <CalendarClock className="h-4 w-4" />
                  Recalculate settlement
                </Button>
              ) : (
                <Button disabled title="Switch to an authorised finance role">
                  Finance approval required
                </Button>
              )
            ) : (
              <LoadingButton loading={paying} loadingText="Posting payment..." onClick={() => void collectPayment()}>
                <CheckCircle2 className="h-4 w-4" />
                Confirm and issue receipt
              </LoadingButton>
            )}
          </DialogFooter>
        </div>
      </CustomDialog>

      <CustomDialog open={Boolean(receipt)} onOpenChange={(open) => !open && setReceipt(null)} title="Payment receipt recorded" description="The repayment, instalment allocation, accounting entry and branch money movement were committed together." contentClassName="sm:max-w-lg">
        <div className="space-y-5 p-6 sm:p-8">
          {receipt ? <div className="rounded-3xl border bg-muted/30 p-5"><div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-700"><CheckCircle2 className="h-6 w-6" /></div><p className="text-xs font-black uppercase tracking-[0.18em] text-muted-foreground">Receipt number</p><p className="mt-2 font-mono text-lg font-black text-primary">{receipt.receipt_number ?? receipt.provider_reference}</p><p className="mt-1 text-xs text-muted-foreground">Payment reference {receipt.provider_reference}</p><p className="mt-1 text-sm font-bold">{methods.find((item) => item.value === receipt.payment_method)?.label ?? titleCase(receipt.payment_method)}</p>{receipt.proof_reference ? <p className="mt-1 text-xs text-muted-foreground">External proof: {receipt.proof_reference}</p> : null}<div className="mt-5 grid grid-cols-2 gap-3"><Value label="Received" value={formatMoney(receipt.preview?.amount_tendered ?? receipt.cash_transaction?.tendered_amount ?? 0)} /><Value label="Applied" value={formatMoney(receipt.preview?.amount_applied ?? receipt.cash_transaction?.applied_amount ?? 0)} /><Value label="Change" value={formatMoney(receipt.preview?.change_amount ?? receipt.cash_transaction?.change_amount ?? 0)} /><Value label="Forward" value={formatMoney(receipt.preview?.forward_amount ?? receipt.cash_transaction?.forward_amount ?? 0)} /></div></div> : null}
          <DialogFooter className="mx-0 mb-0 flex-wrap">{receipt && loan ? <><LoadingButton variant="outline" loading={receiptAction === "download"} loadingText="Downloading..." disabled={receiptAction !== null && receiptAction !== "download"} onClick={() => void downloadReceipt()}><Download className="h-4 w-4" />Download receipt</LoadingButton><LoadingButton variant="outline" loading={receiptAction === "print"} loadingText="Preparing print..." disabled={receiptAction !== null && receiptAction !== "print"} onClick={() => void printReceipt()}><Printer className="h-4 w-4" />Print</LoadingButton></> : null}<Button onClick={() => setReceipt(null)} disabled={receiptAction !== null}>Done</Button></DialogFooter>
        </div>
      </CustomDialog>
    </div>
  );
}

function Value({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return <div className="rounded-2xl border border-border/60 bg-background/70 p-3"><p className="text-[11px] font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p><p className={`mt-1 ${emphasis ? "text-lg text-primary" : "text-sm"} font-black`}>{value}</p></div>;
}
