"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Banknote, Calculator, CheckCircle2, FileText, HandCoins, Plus, RefreshCcw, Search, Send, ShieldCheck } from "lucide-react";

import { listOffersByRequest } from "@/api/loanOffers";
import { acceptLoanOffer, createLoanRequest, listMyLoanRequests } from "@/api/loanRequests";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { interestMethodLabel } from "@/lib/interest-methods";
import type { LoanOffer } from "@/types/loan_offer";
import type { LoanRequest } from "@/types/loanRequest";
import { toast } from "@/utils/toast";

const EMPTY_FORM = { amount: "", term: "3", purpose: "", allowCalls: true };

export default function BorrowerRequestsPage() {
  const [requests, setRequests] = useState<LoanRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [feeRequest, setFeeRequest] = useState<LoanRequest | null>(null);
  const [offersRequest, setOffersRequest] = useState<LoanRequest | null>(null);
  const [offers, setOffers] = useState<LoanOffer[]>([]);
  const [offersLoading, setOffersLoading] = useState(false);
  const [acceptingId, setAcceptingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRequests(await listMyLoanRequests());
    } catch (error) {
      toast.error(error, { description: "Your loan requests could not be loaded." });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const filtered = useMemo(() => {
    const value = search.trim().toLowerCase();
    if (!value) return requests;
    return requests.filter((request) => [request.id, request.loan_purpose, request.status, request.service_fee_status]
      .some((item) => String(item ?? "").toLowerCase().includes(value)));
  }, [requests, search]);

  const sortedOffers = useMemo(() => [...offers].sort((a, b) => Number(a.total_repayment ?? Number.MAX_SAFE_INTEGER) - Number(b.total_repayment ?? Number.MAX_SAFE_INTEGER)), [offers]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const created = await createLoanRequest({
        requested_amount: Number(form.amount),
        preferred_term_months: Number(form.term),
        loan_purpose: form.purpose.trim(),
        visible_to_lenders: true,
        allow_lenders_to_call: form.allowCalls,
      });
      setRequests((current) => [created, ...current]);
      setCreateOpen(false);
      setForm(EMPTY_FORM);
      if (created.service_fee_status === "required" && Number(created.service_fee_amount) > 0) {
        setFeeRequest(created);
        toast.info("Service fee payment required", { description: "The request remains private until an authorised platform finance user records and verifies the fee payment." });
      } else {
        toast.success("Loan request opened", { description: "Eligible lending companies can now review it." });
      }
    } catch (error) {
      toast.error(error, { description: "The loan request could not be created." });
    } finally {
      setSubmitting(false);
    }
  }

  async function openOffers(request: LoanRequest) {
    setOffersRequest(request);
    setOffersLoading(true);
    try {
      setOffers(await listOffersByRequest(request.id));
    } catch (error) {
      toast.error(error, { description: "Lender offers could not be loaded." });
      setOffers([]);
    } finally {
      setOffersLoading(false);
    }
  }

  async function accept(offer: LoanOffer) {
    if (!offersRequest) return;
    setAcceptingId(offer.id);
    try {
      const loan = await acceptLoanOffer(offersRequest.id, offer.id);
      toast.success("Loan offer accepted", { description: `Your loan number is ${loan.loan_reference}. The agreement must be generated and fully signed before the company can disburse funds.` });
      setOffersRequest(null);
      await load();
    } catch (error) {
      toast.error(error, { description: "The offer could not be accepted." });
    } finally {
      setAcceptingId(null);
    }
  }

  if (loading) return <PageLoader rows={6} />;

  return (
    <div className="loanhub-page">
      <section className="loanhub-hero flex flex-col justify-between gap-5 p-6 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Online borrowing</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">My loan requests</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">Create a marketplace request, settle any configured service fee through a recognised payment method, compare offers calculated with the lenders’ selected interest methods, and accept the best suitable company offer.</p>
        </div>
        <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh</Button><Button onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4" />New request</Button></div>
      </section>

      <Alert>
        <Banknote className="h-4 w-4" />
        <AlertTitle>Recognised payment channels</AlertTitle>
        <AlertDescription>LoanHub identifies the payment channel and records manually verified proof for non-cash methods. No live wallet or bank integration is implied until a provider adapter is enabled.</AlertDescription>
      </Alert>

      <Card className="loanhub-panel overflow-visible">
        <StickyFilterBar
          ariaLabel="Loan request history search"
          className="rounded-t-3xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
        >
          <CardHeader className="rounded-[inherit] border-b bg-muted/20">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><CardTitle>Request history</CardTitle><CardDescription>Draft requests with unpaid service fees are not shown to lenders.</CardDescription></div><SuggestionSearch
                value={search}
                onValueChange={setSearch}
                suggestions={requests.map((request) => ({
                  value: request.loan_purpose?.trim() || request.id,
                  label: request.loan_purpose?.trim() || `Request ${request.id.slice(0, 8)}`,
                  description: `${titleCase(request.status)} · ${formatMoney(request.requested_amount)}`,
                  keywords: [request.id, request.status, request.service_fee_status],
                }))}
                placeholder="Type to search requests..."
                suggestionLabel="Loan requests"
                emptyMessage="No request matches that text."
                wrapperClassName="w-full sm:max-w-sm"
              /></div>
          </CardHeader>
        </StickyFilterBar>
        <CardContent className="overflow-hidden rounded-b-3xl p-5 sm:p-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.length === 0 ? <div className="col-span-full flex min-h-64 flex-col items-center justify-center text-center text-muted-foreground"><FileText className="mb-3 h-10 w-10" /><p>No loan requests match the current search.</p></div> : filtered.map((request) => {
              const needsFee = request.service_fee_status === "required" || request.service_fee_status === "processing" || request.service_fee_status === "failed";
              return <article key={request.id} className="rounded-[1.5rem] border border-border/70 bg-card p-5 shadow-sm">
                <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-[0.14em] text-muted-foreground">Requested</p><p className="mt-1 text-2xl font-black">{formatMoney(request.requested_amount)}</p></div><Badge variant={request.status === "open" || request.status === "accepted" ? "default" : "secondary"}>{titleCase(request.status)}</Badge></div>
                <p className="mt-4 line-clamp-3 min-h-16 text-sm leading-6 text-muted-foreground">{request.loan_purpose || "No purpose supplied"}</p>
                <div className="mt-4 grid grid-cols-2 gap-2"><Value label="Term" value={`${request.preferred_term_months ?? "—"} months`} /><Value label="Created" value={formatDate(request.created_at)} /><Value label="Service fee" value={formatMoney(request.service_fee_amount, request.service_fee_currency)} /><Value label="Fee status" value={titleCase(request.service_fee_status)} /></div>
                {needsFee ? <Button className="mt-5 w-full" variant="outline" onClick={() => setFeeRequest(request)}><Banknote className="h-4 w-4" />Service fee instructions</Button> : <Button className="mt-5 w-full" onClick={() => void openOffers(request)} disabled={!['open','offered','accepted'].includes(request.status)}><Calculator className="h-4 w-4" />Compare offers</Button>}
              </article>;
            })}
          </div>
        </CardContent>
      </Card>

      <CustomDialog
        open={createOpen}
        onOpenChange={(open) => !submitting && setCreateOpen(open)}
        title="Create an online loan request"
        description="The system snapshots the owner-configured borrower request fee when this request is created."
        contentClassName="sm:max-w-xl"
      >
        <form onSubmit={submit} className="space-y-6 p-6 sm:p-8">
          <div className="space-y-4">
            <Field label="Amount needed"><Input type="number" min="1" step="0.01" required value={form.amount} onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))} /></Field>
            <Field label="Preferred term (months)"><Input type="number" min="1" max="120" required value={form.term} onChange={(event) => setForm((current) => ({ ...current, term: event.target.value }))} /></Field>
            <Field label="Loan purpose"><Textarea required rows={4} value={form.purpose} onChange={(event) => setForm((current) => ({ ...current, purpose: event.target.value }))} placeholder="Explain how the loan will be used" /></Field>
            <label className="flex items-start gap-3 rounded-2xl border bg-muted/25 p-4"><Checkbox checked={form.allowCalls} onCheckedChange={(checked) => setForm((current) => ({ ...current, allowCalls: checked === true }))} /><span><span className="block text-sm font-black">Allow eligible lenders to call</span><span className="mt-1 block text-xs leading-5 text-muted-foreground">Only companies that obtain permitted access can use the contact details.</span></span></label>
          </div>
          <DialogFooter className="mx-0 mb-0"><Button type="button" variant="outline" onClick={() => setCreateOpen(false)} disabled={submitting}>Cancel</Button><LoadingButton type="submit" loading={submitting} loadingText="Creating..."><Send className="h-4 w-4" />Create request</LoadingButton></DialogFooter>
        </form>
      </CustomDialog>

      <CustomDialog
        open={Boolean(feeRequest)}
        onOpenChange={(open) => !open && setFeeRequest(null)}
        title="Pay the request service fee"
        description="The platform owner configured this fee. Authorized platform finance must record it before the request is broadcast."
        contentClassName="sm:max-w-lg"
      >
        <div className="space-y-5 p-6 sm:p-8">
          {feeRequest && <div className="space-y-4"><div className="rounded-3xl border bg-gradient-to-br from-amber-500/10 to-primary/8 p-5"><div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-700"><Banknote className="h-6 w-6" /></div><p className="text-xs font-black uppercase tracking-[0.14em] text-muted-foreground">Amount due</p><p className="mt-1 text-3xl font-black">{formatMoney(feeRequest.service_fee_amount, feeRequest.service_fee_currency)}</p><p className="mt-3 font-mono text-xs font-black text-primary">REQUEST ID: {feeRequest.id}</p></div><ol className="space-y-3 text-sm leading-6 text-muted-foreground"><li><strong className="text-foreground">1.</strong> Take the fee and this request ID to the LoanHub platform finance desk or use an approved channel supplied by the platform.</li><li><strong className="text-foreground">2.</strong> Platform finance verifies your identity and the payment evidence before posting the transaction.</li><li><strong className="text-foreground">3.</strong> The system issues a receipt and automatically opens the request to lenders after verification.</li></ol><Alert><ShieldCheck className="h-4 w-4" /><AlertTitle>Protect your payment credentials</AlertTitle><AlertDescription>LoanHub staff may request proof of payment, but must never ask for wallet PINs, bank passwords or one-time passwords.</AlertDescription></Alert></div>}
          <DialogFooter className="mx-0 mb-0"><Button onClick={() => setFeeRequest(null)}>I understand</Button></DialogFooter>
        </div>
      </CustomDialog>

      <CustomDialog
        open={Boolean(offersRequest)}
        onOpenChange={(open) => !open && setOffersRequest(null)}
        title="Compare lender offers"
        description="Compare each offer’s interest method, approved principal, instalment and total repayment before accepting."
        contentClassName="sm:max-w-5xl"
      >
        <div className="space-y-5 p-6 sm:p-8">
          {offersLoading ? <div className="py-20"><PageLoader rows={3} /></div> : sortedOffers.length === 0 ? <div className="py-20 text-center text-muted-foreground"><HandCoins className="mx-auto mb-3 h-10 w-10" />No company has submitted an offer yet.</div> : <div className="grid gap-4 md:grid-cols-2">{sortedOffers.map((offer, index) => <article key={offer.id} className={`rounded-3xl border p-5 ${index === 0 ? "border-primary bg-primary/5 ring-2 ring-primary/10" : "bg-card"}`}><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">Approved principal</p><p className="mt-1 text-2xl font-black">{formatMoney(offer.approved_amount)}</p></div>{index === 0 && <Badge>Lowest total</Badge>}</div><div className="mt-5 grid grid-cols-2 gap-3"><Value label="Monthly" value={formatMoney(offer.monthly_repayment)} /><Value label="Total" value={formatMoney(offer.total_repayment)} /><Value label="Rate" value={`${offer.interest_rate_percent ?? 0}%`} /><Value label="Method" value={interestMethodLabel(offer.calculation_method)} /><Value label="Term" value={`${offer.term_months} months`} /></div>{offer.notes && <p className="mt-4 rounded-2xl bg-muted/40 p-3 text-sm text-muted-foreground">{offer.notes}</p>}<LoadingButton className="mt-5 w-full" loading={acceptingId === offer.id} loadingText="Accepting..." disabled={acceptingId !== null || offer.status !== "pending"} onClick={() => void accept(offer)}><CheckCircle2 className="h-4 w-4" />Accept this offer</LoadingButton></article>)}</div>}
          <DialogFooter className="mx-0 mb-0"><Button variant="outline" onClick={() => setOffersRequest(null)}>Close</Button></DialogFooter>
        </div>
      </CustomDialog>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) { return <div className="space-y-2"><Label>{label}</Label>{children}</div>; }
function Value({ label, value }: { label: string; value: string }) { return <div className="rounded-2xl border bg-muted/25 p-3"><p className="text-[11px] font-black uppercase tracking-[0.1em] text-muted-foreground">{label}</p><p className="mt-1 text-sm font-black">{value}</p></div>; }
