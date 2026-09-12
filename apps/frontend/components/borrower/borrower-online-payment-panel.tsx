"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarClock, ExternalLink, FileSignature, Loader2, RefreshCcw, ShieldCheck, WalletCards } from "lucide-react";

import {
  createBorrowerGatewayCheckout,
  createBorrowerSettlementCheckout,
  createBorrowerSettlementQuote,
  getGatewayPaymentMethods,
  type BorrowerSettlementQuote,
  type GatewayPaymentRail,
} from "@/api/lelefaPayGate";
import { loanPaymentOperationsApi } from "@/api/loanPaymentOperations";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createIdempotencyKey, formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { toast } from "@/utils/toast";

function nextOutstanding(loan: { balance: number; installments: Array<{ is_superseded: boolean; status: string; total_due: number; paid_amount: number }> }) {
  const installment = loan.installments.find(item => !item.is_superseded && ["pending", "partially_paid", "overdue"].includes(item.status));
  return installment ? Math.max(0, Number(installment.total_due) - Number(installment.paid_amount)) : Math.max(0, Number(loan.balance));
}

function futureDate(days: number) {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

export function BorrowerOnlinePaymentPanel() {
  const { loans } = useAppData();
  const activeLoans = useMemo(() => loans.filter(loan => ["active", "defaulted"].includes(loan.status) && Number(loan.balance) > 0), [loans]);
  const [loanId, setLoanId] = useState("");
  const [amount, setAmount] = useState("");
  const [rails, setRails] = useState<GatewayPaymentRail[]>([]);
  const [railsLoading, setRailsLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [quote, setQuote] = useState<BorrowerSettlementQuote | null>(null);
  const [quoteAccepted, setQuoteAccepted] = useState(false);
  const [settlementBusy, setSettlementBusy] = useState(false);
  const [mandateAuthorized, setMandateAuthorized] = useState(false);
  const [mandateBusy, setMandateBusy] = useState(false);
  const [firstDebitDate, setFirstDebitDate] = useState(futureDate(30));
  const [restructureTerm, setRestructureTerm] = useState("6");
  const [restructureReason, setRestructureReason] = useState("");
  const [operationsBusy, setOperationsBusy] = useState(false);
  const [remindersEnabled, setRemindersEnabled] = useState(true);

  const selectedLoan = activeLoans.find(loan => loan.id === loanId) ?? null;
  const mandateRail = rails.find(rail => rail.provider === "mpesa" && rail.flow === "phone_prompt");

  useEffect(() => { if (!loanId && activeLoans[0]) setLoanId(activeLoans[0].id); }, [activeLoans, loanId]);
  useEffect(() => { if (selectedLoan) { setAmount(nextOutstanding(selectedLoan).toFixed(2)); setQuote(null); setQuoteAccepted(false); } }, [selectedLoan]);
  useEffect(() => {
    getGatewayPaymentMethods("LSL")
      .then(catalog => setRails(catalog.methods.filter(rail => rail.available)))
      .catch(error => toast.error(error, { description: "LelefaPayGate payment methods could not be loaded." }))
      .finally(() => setRailsLoading(false));
  }, []);

  async function continueToGateway() {
    const numericAmount = Number(amount);
    if (!selectedLoan || !Number.isFinite(numericAmount) || numericAmount <= 0) return toast.warning("Select a loan and enter a positive payment amount.");
    if (numericAmount > Number(selectedLoan.balance) + 0.0001) return toast.warning("The payment cannot exceed the current loan balance.");
    if (!rails.length) return toast.warning("No LelefaPayGate payment method is currently enabled for LSL.");
    setSubmitting(true);
    try {
      const checkout = await createBorrowerGatewayCheckout(selectedLoan.id, { amount: numericAmount, idempotency_key: createIdempotencyKey(`borrower-online-${selectedLoan.id}`) });
      window.location.assign(checkout.checkout_url);
    } catch (error) {
      toast.error(error, { description: "The secure checkout could not be opened. If this closes future instalments, use the settlement quote below." });
      setSubmitting(false);
    }
  }

  async function loadSettlementQuote() {
    if (!selectedLoan) return;
    setSettlementBusy(true);
    try {
      setQuote(await createBorrowerSettlementQuote(selectedLoan.id, { settlement_date: new Date().toISOString().slice(0, 10), valid_for_days: 3 }));
    } catch (error) { toast.error(error, { description: "The settlement quote could not be calculated." }); }
    finally { setSettlementBusy(false); }
  }

  async function paySettlement() {
    if (!selectedLoan || !quote || !quoteAccepted) return toast.warning("Accept the settlement amount before continuing.");
    setSettlementBusy(true);
    try {
      const checkout = await createBorrowerSettlementCheckout(selectedLoan.id, quote.id, { borrower_acknowledged: true, agreement_note: "Borrower accepted the online early-settlement quote", idempotency_key: createIdempotencyKey(`borrower-settlement-${quote.id}`) });
      window.location.assign(checkout.checkout_url);
    } catch (error) { toast.error(error, { description: "The settlement checkout could not be opened." }); setSettlementBusy(false); }
  }

  async function createMandate() {
    if (!selectedLoan || !mandateRail || !mandateAuthorized) return toast.warning("Select a supported mobile-money rail and authorise the recurring debit mandate.");
    setMandateBusy(true);
    try {
      await loanPaymentOperationsApi.createMandate({ loan_id: selectedLoan.id, provider: mandateRail.provider, amount: nextOutstanding(selectedLoan), first_debit_date: firstDebitDate, consent_reference: `PORTAL-${Date.now()}`, borrower_authorized: true });
      toast.success("Automatic repayment mandate submitted", { description: "It becomes active only after LelefaPayGate and the provider confirm it." });
      setMandateAuthorized(false);
    } catch (error) { toast.error(error, { description: "The automatic repayment mandate could not be created." }); }
    finally { setMandateBusy(false); }
  }

  async function saveReminders() {
    if (!selectedLoan) return;
    setOperationsBusy(true);
    try {
      await loanPaymentOperationsApi.saveReminderPreferences(selectedLoan.company_id, { in_app_enabled: remindersEnabled, sms_enabled: false, email_enabled: false, whatsapp_enabled: false, days_before_due: 3, remind_on_due_date: true, overdue_interval_days: 3, payment_link_enabled: true, timezone: "Africa/Maseru" });
      toast.success("Repayment reminder preference saved");
    } catch (error) { toast.error(error, { description: "Reminder preferences could not be saved." }); }
    finally { setOperationsBusy(false); }
  }

  async function requestRestructure() {
    if (!selectedLoan || restructureReason.trim().length < 10) return toast.warning("Explain why you need the repayment arrangement changed.");
    setOperationsBusy(true);
    try {
      const result = await loanPaymentOperationsApi.requestRestructure({ loan_id: selectedLoan.id, requested_term_months: Number(restructureTerm), payment_holiday_days: 0, reason: restructureReason.trim(), borrower_accepted: true });
      toast.success("Restructure request submitted", { description: `Proposed instalment: ${String(result.preview.monthly_installment ?? "calculated")}` });
      setRestructureReason("");
    } catch (error) { toast.error(error, { description: "The restructure request could not be created." }); }
    finally { setOperationsBusy(false); }
  }

  return <div className="space-y-5">
    <Card className="loanhub-panel overflow-hidden">
      <CardHeader className="border-b bg-gradient-to-br from-primary/10 via-background to-emerald-500/10"><CardTitle className="flex items-center gap-2"><WalletCards className="h-5 w-5 text-primary" />Pay a loan online</CardTitle><CardDescription>Choose the loan and amount, then complete payment on LelefaPayGate using an enabled provider.</CardDescription></CardHeader>
      <CardContent className="space-y-5 p-5 sm:p-6">
        <Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Secure hosted payment</AlertTitle><AlertDescription>LoanHub never asks for your PIN or card details. Your loan updates only after a signed LelefaPayGate confirmation.</AlertDescription></Alert>
        {activeLoans.length ? <>
          <div className="grid gap-4 md:grid-cols-2"><div className="space-y-2"><Label>Loan to pay</Label><Select value={loanId} onValueChange={setLoanId} disabled={submitting}><SelectTrigger><SelectValue placeholder="Select an active loan" /></SelectTrigger><SelectContent>{activeLoans.map(loan => <SelectItem key={loan.id} value={loan.id}>{loan.loan_reference} · {formatMoney(loan.balance)}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label htmlFor="borrower-online-amount">Amount to pay</Label><Input id="borrower-online-amount" type="number" min="0.01" step="0.01" max={selectedLoan?.balance} value={amount} disabled={submitting} onChange={event=>setAmount(event.target.value)} /></div></div>
          <div className="rounded-2xl border bg-muted/20 p-4"><p className="text-xs font-black uppercase tracking-[0.14em] text-muted-foreground">Available through LelefaPayGate</p>{railsLoading?<p className="mt-3 flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading payment methods…</p>:rails.length?<div className="mt-3 flex flex-wrap gap-2">{rails.map(rail=><span key={rail.id} className="rounded-full border bg-background px-3 py-1.5 text-xs font-bold">{rail.label}</span>)}</div>:<p className="mt-3 text-sm text-amber-700">No online LSL payment rail is enabled right now.</p>}</div>
          <Button className="h-12 w-full" onClick={()=>void continueToGateway()} disabled={submitting||railsLoading||!rails.length}>{submitting?<Loader2 className="h-4 w-4 animate-spin"/>:<ExternalLink className="h-4 w-4"/>}{submitting?"Opening secure checkout…":"Continue to LelefaPayGate"}</Button>
        </>:<p className="rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground">You do not currently have an active loan that accepts repayments.</p>}
      </CardContent>
    </Card>

    {selectedLoan ? <div className="grid gap-5 xl:grid-cols-2">
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><RefreshCcw className="h-5 w-5" />Settle early with reduced future interest</CardTitle><CardDescription>LoanHub recalculates earned interest and removes the unearned future portion before payment.</CardDescription></CardHeader><CardContent className="space-y-4">{quote?<><div className="grid grid-cols-2 gap-3 rounded-2xl border p-4 text-sm"><div><p className="text-muted-foreground">Settlement amount</p><b>{formatMoney(Number(quote.settlement_amount))}</b></div><div><p className="text-muted-foreground">Interest rebate</p><b className="text-emerald-700">{formatMoney(Number(quote.unearned_interest_rebate))}</b></div><div><p className="text-muted-foreground">Chargeable periods</p><b>{quote.chargeable_periods}</b></div><div><p className="text-muted-foreground">Expires</p><b>{new Date(quote.quote_expires_at).toLocaleDateString()}</b></div></div><label className="flex items-start gap-3 text-sm"><Checkbox checked={quoteAccepted} onCheckedChange={value=>setQuoteAccepted(Boolean(value))}/><span>I accept this recalculated settlement and understand it will close the loan after confirmed payment.</span></label><Button className="w-full" disabled={!quoteAccepted||settlementBusy} onClick={()=>void paySettlement()}>{settlementBusy?<Loader2 className="h-4 w-4 animate-spin"/>:<ExternalLink className="h-4 w-4"/>}Pay settlement through Lelefa</Button></>:<Button variant="outline" className="w-full" disabled={settlementBusy} onClick={()=>void loadSettlementQuote()}>{settlementBusy?<Loader2 className="h-4 w-4 animate-spin"/>:<RefreshCcw className="h-4 w-4"/>}Calculate settlement quote</Button>}</CardContent></Card>
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><CalendarClock className="h-5 w-5" />Automatic repayment</CardTitle><CardDescription>Create a revocable provider mandate. No deduction happens without your explicit consent and provider confirmation.</CardDescription></CardHeader><CardContent className="space-y-4"><div className="space-y-2"><Label>First debit date</Label><Input type="date" min={futureDate(1)} value={firstDebitDate} onChange={e=>setFirstDebitDate(e.target.value)}/></div><label className="flex items-start gap-3 text-sm"><Checkbox checked={mandateAuthorized} onCheckedChange={value=>setMandateAuthorized(Boolean(value))}/><span>I authorise monthly collection of the due instalment from my verified {mandateRail?.label??"mobile-money"} account. I can revoke this mandate.</span></label><Button className="w-full" disabled={!mandateAuthorized||!mandateRail||mandateBusy} onClick={()=>void createMandate()}>{mandateBusy?<Loader2 className="h-4 w-4 animate-spin"/>:<FileSignature className="h-4 w-4"/>}Submit automatic repayment mandate</Button></CardContent></Card>
      <Card><CardHeader><CardTitle>Repayment reminders</CardTitle><CardDescription>In-app reminders are ready. SMS, email and WhatsApp stay off until approved connectors are configured.</CardDescription></CardHeader><CardContent className="space-y-4"><label className="flex items-center gap-3 text-sm"><Checkbox checked={remindersEnabled} onCheckedChange={value=>setRemindersEnabled(Boolean(value))}/><span>Notify me three days before, on the due date and while overdue.</span></label><Button variant="outline" className="w-full" disabled={operationsBusy} onClick={()=>void saveReminders()}>Save reminder preference</Button></CardContent></Card>
      <Card><CardHeader><CardTitle>Request a new repayment arrangement</CardTitle><CardDescription>The lender sees an auditable calculator preview and must approve a replacement agreement before the schedule changes.</CardDescription></CardHeader><CardContent className="space-y-3"><div className="space-y-2"><Label>Requested remaining months</Label><Input type="number" min="1" max="120" value={restructureTerm} onChange={e=>setRestructureTerm(e.target.value)}/></div><div className="space-y-2"><Label>Reason</Label><Input value={restructureReason} onChange={e=>setRestructureReason(e.target.value)} placeholder="Explain the change in your circumstances"/></div><Button variant="outline" className="w-full" disabled={operationsBusy} onClick={()=>void requestRestructure()}>Submit restructure request</Button></CardContent></Card>
    </div>:null}
  </div>;
}
