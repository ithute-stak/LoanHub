"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { BadgePercent, Banknote, CheckCircle2, FileWarning, ReceiptText, RefreshCcw, Scale } from "lucide-react";

import {
  decideCompanyClaim,
  listCompanyAgreements,
  listCompanyChargeClaims,
  listCompanyChargeLedger,
  makeCompanyAgreementDecision,
  settleCompanyClaim,
  type ChargeClaim,
  type ChargeLedgerEntry,
  type TransactionAgreement,
} from "@/api/finance";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { DEFAULT_PAYMENT_METHOD_OPTIONS, EMPTY_PAYMENT_EVIDENCE, PaymentMethodFields, type PaymentEvidence } from "@/components/payments/payment-method-fields";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { PageLoader } from "@/components/ui/page-loader";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { createIdempotencyKey, formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import { toast } from "@/utils/toast";

export default function CompanyFinancePage() {
  const [agreements, setAgreements] = useState<TransactionAgreement[]>([]);
  const [ledger, setLedger] = useState<ChargeLedgerEntry[]>([]);
  const [claims, setClaims] = useState<ChargeClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [decisionAgreement, setDecisionAgreement] = useState<TransactionAgreement | null>(null);
  const [claim, setClaim] = useState<ChargeClaim | null>(null);
  const [claimAction, setClaimAction] = useState<"acknowledge" | "dispute" | "settle">("acknowledge");
  const [reason, setReason] = useState("");
  const [settlementEvidence, setSettlementEvidence] = useState<PaymentEvidence>(EMPTY_PAYMENT_EVIDENCE);
  const [confirmAgreement, setConfirmAgreement] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [agreementRows, ledgerRows, claimRows] = await Promise.all([
        listCompanyAgreements(),
        listCompanyChargeLedger(),
        listCompanyChargeClaims(),
      ]);
      setAgreements(agreementRows);
      setLedger(ledgerRows);
      setClaims(claimRows);
    } catch (error) {
      toast.error(error, { description: "Company charge bookkeeping could not be loaded." });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const accrued = useMemo(() => ledger.filter((item) => item.status === "accrued" || item.status === "claimed").reduce((sum, item) => sum + Number(item.charge_amount), 0), [ledger]);
  const openClaims = useMemo(() => claims.filter((item) => !["paid", "settled"].includes(item.status)).reduce((sum, item) => sum + Number(item.amount), 0), [claims]);
  const activeAgreement = useMemo(() => agreements.find((item) => item.status === "active") ?? null, [agreements]);

  async function acceptAgreement() {
    if (!decisionAgreement) return;
    setWorking(true);
    try {
      await makeCompanyAgreementDecision(decisionAgreement.id, true);
      toast.success("Company acceptance recorded");
      setConfirmAgreement(false);
      setDecisionAgreement(null);
      await load();
    } catch (error) { toast.error(error); } finally { setWorking(false); }
  }

  function openClaimAction(item: ChargeClaim, action: "acknowledge" | "dispute" | "settle") {
    setClaim(item);
    setClaimAction(action);
    setReason("");
    setSettlementEvidence(EMPTY_PAYMENT_EVIDENCE);
  }

  async function submitClaimAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!claim) return;
    setWorking(true);
    try {
      if (claimAction === "settle") {
        const result = await settleCompanyClaim(claim.id, {
          payment_method: settlementEvidence.payment_method,
          proof_reference: settlementEvidence.proof_reference.trim() || null,
          proof_url: settlementEvidence.proof_url.trim() || null,
          proof_notes: settlementEvidence.proof_notes.trim() || null,
          notes: reason.trim() || null,
          idempotency_key: createIdempotencyKey(`claim-${claim.id}`),
        });
        toast.success("Claim settlement recorded", { description: `Payment reference ${result.provider_reference} was recorded.` });
      } else {
        await decideCompanyClaim(claim.id, claimAction, reason.trim() || undefined);
        toast.success(claimAction === "acknowledge" ? "Claim acknowledged" : "Claim disputed");
      }
      setClaim(null);
      await load();
    } catch (error) { toast.error(error); } finally { setWorking(false); }
  }

  if (loading) return <PageLoader rows={7} />;

  return (
    <div className="loanhub-page">
      <section className="loanhub-hero flex flex-col justify-between gap-5 p-6 lg:flex-row lg:items-end">
        <div><p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Joint bookkeeping</p><h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Platform agreements and transaction charges</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">Review the company’s agreed money-in and money-out rates, every automatically accrued charge, and period claims issued by the platform owner.</p></div>
        <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh records</Button>
      </section>

      <div className="grid gap-4 md:grid-cols-3"><Metric icon={Scale} label="Active agreement" value={activeAgreement?.agreement_number ?? "None"} /><Metric icon={BadgePercent} label="Accrued charges" value={formatMoney(accrued)} /><Metric icon={ReceiptText} label="Open claims" value={formatMoney(openClaims)} /></div>

      <Alert><BadgePercent className="h-4 w-4" /><AlertTitle>Transparent calculation</AlertTitle><AlertDescription>The ledger stores the gross money movement, payment channel, direction, percentage rate, flat fee and final charge. At 0.005%, M10,000 creates a charge of M0.50 before any agreed minimum or maximum.</AlertDescription></Alert>

      <Tabs defaultValue="agreements" className="space-y-5"><TabsList className="grid h-auto w-full grid-cols-3 rounded-2xl p-1"><TabsTrigger value="agreements" className="rounded-xl py-2.5">Agreements</TabsTrigger><TabsTrigger value="ledger" className="rounded-xl py-2.5">Charge ledger</TabsTrigger><TabsTrigger value="claims" className="rounded-xl py-2.5">Claims</TabsTrigger></TabsList>
        <TabsContent value="agreements"><Card className="loanhub-panel overflow-hidden"><CardHeader><CardTitle>Transaction agreements</CardTitle><CardDescription>Both platform owner and company must accept before a charge agreement becomes active.</CardDescription></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Agreement</TableHead><TableHead>Money in</TableHead><TableHead>Money out</TableHead><TableHead>Period</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{agreements.length === 0 ? <TableRow><TableCell colSpan={6} className="h-40 text-center text-muted-foreground">No agreement has been issued to this company.</TableCell></TableRow> : agreements.map((item) => <TableRow key={item.id}><TableCell><p className="font-black">{item.name}</p><p className="font-mono text-xs text-muted-foreground">{item.agreement_number}</p></TableCell><TableCell>{item.inbound_percentage}% + {formatMoney(item.inbound_flat_fee)}</TableCell><TableCell>{item.outbound_percentage}% + {formatMoney(item.outbound_flat_fee)}</TableCell><TableCell>{formatDate(item.effective_from)}{item.effective_to ? ` – ${formatDate(item.effective_to)}` : " onward"}</TableCell><TableCell><Badge variant={item.status === "active" ? "default" : "secondary"}>{titleCase(item.status)}</Badge></TableCell><TableCell className="text-right">{!item.company_accepted_at && !["rejected", "active"].includes(item.status) && <Button size="sm" onClick={() => { setDecisionAgreement(item); setConfirmAgreement(true); }}><CheckCircle2 className="h-4 w-4" />Accept</Button>}</TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card></TabsContent>
        <TabsContent value="ledger"><Card className="loanhub-panel overflow-hidden"><CardHeader><CardTitle>Automatic company charge ledger</CardTitle><CardDescription>The platform and company see the same source calculations.</CardDescription></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Accrued</TableHead><TableHead>Direction</TableHead><TableHead>Purpose</TableHead><TableHead>Gross</TableHead><TableHead>Rate</TableHead><TableHead>Charge</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{ledger.length === 0 ? <TableRow><TableCell colSpan={7} className="h-40 text-center text-muted-foreground">No transaction charges have accrued.</TableCell></TableRow> : ledger.map((item) => <TableRow key={item.id}><TableCell>{formatDateTime(item.accrued_at)}</TableCell><TableCell><Badge variant="outline">{item.direction === "inbound" ? "Money in" : "Money out"}</Badge></TableCell><TableCell>{titleCase(item.payment_purpose)}</TableCell><TableCell>{formatMoney(item.gross_amount, item.currency)}</TableCell><TableCell>{item.percentage_rate}% + {formatMoney(item.flat_fee, item.currency)}</TableCell><TableCell className="font-black">{formatMoney(item.charge_amount, item.currency)}</TableCell><TableCell><Badge variant="secondary">{titleCase(item.status)}</Badge></TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card></TabsContent>
        <TabsContent value="claims"><Card className="loanhub-panel overflow-hidden"><CardHeader><CardTitle>Platform claims</CardTitle><CardDescription>Acknowledge, dispute with a reason, or settle an eligible claim using any recognised payment channel with verified evidence.</CardDescription></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Claim</TableHead><TableHead>Period</TableHead><TableHead>Transactions</TableHead><TableHead>Amount</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{claims.length === 0 ? <TableRow><TableCell colSpan={6} className="h-40 text-center text-muted-foreground">No claims have been issued.</TableCell></TableRow> : claims.map((item) => <TableRow key={item.id}><TableCell><p className="font-mono text-xs font-black text-primary">{item.claim_number}</p><p className="text-xs text-muted-foreground">Due {formatDate(item.due_at)}</p></TableCell><TableCell>{formatDate(item.period_start)} – {formatDate(item.period_end)}</TableCell><TableCell>{item.transaction_count}</TableCell><TableCell className="font-black">{formatMoney(item.amount, item.currency)}</TableCell><TableCell><Badge variant={item.status === "paid" ? "default" : "secondary"}>{titleCase(item.status)}</Badge></TableCell><TableCell><div className="flex justify-end gap-2">{item.status === "issued" && <><Button size="sm" variant="outline" onClick={() => openClaimAction(item, "acknowledge")}>Acknowledge</Button><Button size="sm" variant="outline" onClick={() => openClaimAction(item, "dispute")}><FileWarning className="h-4 w-4" />Dispute</Button></>}{["issued", "acknowledged", "disputed"].includes(item.status) && <Button size="sm" onClick={() => openClaimAction(item, "settle")}><Banknote className="h-4 w-4" />Settle claim</Button>}</div></TableCell></TableRow>)}</TableBody></Table></div></CardContent></Card></TabsContent>
      </Tabs>

      <ConfirmDialog open={confirmAgreement} onOpenChange={setConfirmAgreement} title="Accept transaction agreement?" description={decisionAgreement ? `You are accepting ${decisionAgreement.inbound_percentage}% on cash-in and ${decisionAgreement.outbound_percentage}% on cash-out transactions under ${decisionAgreement.agreement_number}.` : "Review the agreement before accepting."} confirmLabel="Accept agreement" loading={working} onConfirm={acceptAgreement} />

      <CustomDialog
        open={Boolean(claim)}
        onOpenChange={(open) => !open && !working && setClaim(null)}
        title={claimAction === "settle" ? "Settle platform claim" : claimAction === "dispute" ? "Dispute platform claim" : "Acknowledge platform claim"}
        description={claim ? `${claim.claim_number} · ${formatMoney(claim.amount, claim.currency)}` : undefined}
        contentClassName="sm:max-w-lg"
      >
        <form onSubmit={submitClaimAction} className="space-y-6 p-6 sm:p-8">
          <div className="space-y-4">
            {claimAction === "settle" ? (
              <>
                <Alert><Banknote className="h-4 w-4" /><AlertTitle>Verified settlement evidence</AlertTitle><AlertDescription>Select how the money moved. Non-cash channels require a reference or proof document before LoanHub posts the company money-out entry.</AlertDescription></Alert>
                <PaymentMethodFields methods={DEFAULT_PAYMENT_METHOD_OPTIONS} value={settlementEvidence} onChange={setSettlementEvidence} />
              </>
            ) : null}
            <div className="space-y-2"><Label>{claimAction === "dispute" ? "Dispute reason" : "Notes"}</Label><Textarea required={claimAction === "dispute"} value={reason} onChange={(event) => setReason(event.target.value)} placeholder={claimAction === "dispute" ? "Explain the exact ledger entries or calculation being disputed" : "Optional finance note"} /></div>
          </div>
          <DialogFooter className="mx-0 mb-0"><Button type="button" variant="outline" onClick={() => setClaim(null)} disabled={working}>Cancel</Button><LoadingButton type="submit" loading={working} loadingText="Recording..." disabled={claimAction === "dispute" && !reason.trim()}>{claimAction === "settle" ? <Banknote className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}{claimAction === "settle" ? "Confirm settlement" : claimAction === "dispute" ? "Submit dispute" : "Acknowledge claim"}</LoadingButton></DialogFooter>
        </form>
      </CustomDialog>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Scale; label: string; value: string }) { return <div className="loanhub-stat"><div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/12 text-primary"><Icon className="h-5 w-5" /></div><p className="mt-4 text-xs font-black uppercase tracking-[0.14em] text-muted-foreground">{label}</p><p className="mt-1 text-xl font-black">{value}</p></div>; }
