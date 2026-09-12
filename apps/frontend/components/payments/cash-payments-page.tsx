"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, Banknote, RefreshCcw, Search, WalletCards } from "lucide-react";

import { listPayments } from "@/api/payments";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoader } from "@/components/ui/page-loader";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { PaymentTransaction } from "@/types/payment";
import { toast } from "@/utils/toast";

export function CashPaymentsPage({ title, description }: { title: string; description: string }) {
  const [payments, setPayments] = useState<PaymentTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setPayments(await listPayments());
    } catch (error) {
      toast.error(error, { description: "Payment transactions could not be loaded." });
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
    if (!value) return payments;
    return payments.filter((payment) => [
      payment.provider_reference,
      payment.cash_transaction?.cash_reference,
      payment.payment_method,
      payment.proof_reference,
      payment.purpose,
      payment.direction,
      payment.status,
    ].some((item) => String(item ?? "").toLowerCase().includes(value)));
  }, [payments, search]);

  const inbound = useMemo(() => payments.filter((item) => item.direction === "inbound" && item.status === "succeeded").reduce((sum, item) => sum + Number(item.amount), 0), [payments]);
  const outbound = useMemo(() => payments.filter((item) => item.direction === "outbound" && item.status === "succeeded").reduce((sum, item) => sum + Number(item.amount), 0), [payments]);

  if (loading) return <PageLoader rows={8} />;

  return (
    <div className="loanhub-page pb-24 lg:pb-0">
      <section className="loanhub-hero flex flex-col justify-between gap-5 p-6 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Payment and proof register</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">{title}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
        <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh register</Button>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <Metric icon={ArrowDownLeft} label="Money received" value={formatMoney(inbound)} hint="Successful inbound transactions" tone="emerald" />
        <Metric icon={ArrowUpRight} label="Money paid out" value={formatMoney(outbound)} hint="Successful outbound transactions" tone="amber" />
        <Metric icon={WalletCards} label="Register entries" value={String(payments.length)} hint="Auditable payment records" tone="blue" />
      </div>

      <Card className="loanhub-panel overflow-hidden">
        <CardHeader className="border-b bg-muted/20">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <CardTitle>Payment transaction register</CardTitle>
              <CardDescription>Every recognised payment channel, external proof, amount applied, cash change and forward balance is preserved separately.</CardDescription>
            </div>
            <SuggestionSearch
              value={search}
              onValueChange={setSearch}
              suggestions={payments.map((payment) => ({
                value: payment.cash_transaction?.cash_reference || payment.provider_reference || payment.proof_reference || payment.id,
                label: payment.cash_transaction?.cash_reference || payment.provider_reference || payment.proof_reference || payment.id.slice(0, 8),
                description: `${titleCase(payment.purpose)} · ${formatMoney(payment.amount, payment.currency)}`,
                keywords: [
                  payment.id,
                  payment.payment_method,
                  payment.purpose,
                  payment.direction,
                  payment.status,
                  payment.proof_reference ?? "",
                ],
              }))}
              placeholder="Type a reference, purpose, method or status..."
              suggestionLabel="Payment transactions"
              emptyMessage="No payment matches that text."
              wrapperClassName="w-full sm:max-w-sm"
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="space-y-3 p-4 md:hidden">
            {filtered.length === 0 ? <div className="py-12 text-center text-sm text-muted-foreground"><Banknote className="mx-auto mb-3 h-9 w-9" />No payment transactions match the search.</div> : filtered.map((payment) => {
              const cash = payment.cash_transaction;
              const FlowIcon = payment.direction === "inbound" ? ArrowDownLeft : ArrowUpRight;
              return <article key={payment.id} className="rounded-2xl border bg-card p-4">
                <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-mono text-xs font-black">{cash?.cash_reference ?? payment.provider_reference ?? payment.id.slice(0, 8)}</p><p className="mt-1 text-xs text-muted-foreground">{formatDateTime(payment.completed_at ?? payment.created_at)}</p></div><Badge variant={payment.status === "succeeded" ? "default" : "secondary"}>{titleCase(payment.status)}</Badge></div>
                <p className="mt-3 text-2xl font-black">{formatMoney(cash?.applied_amount ?? payment.amount, payment.currency)}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2"><Badge variant="outline"><FlowIcon className="mr-1 h-3.5 w-3.5" />{payment.direction === "inbound" ? "Money in" : "Money out"}</Badge><Badge variant="outline">{paymentMethodLabel(payment.payment_method)}</Badge><Badge variant="outline">{titleCase(payment.purpose)}</Badge></div>
                {payment.proof_reference ? <p className="mt-3 break-all text-xs text-muted-foreground">Proof: {payment.proof_reference}</p> : null}
                {cash && (Number(cash.change_amount) > 0 || Number(cash.forward_amount) > 0) ? <p className="mt-2 text-xs text-muted-foreground">Change {formatMoney(cash.change_amount, payment.currency)} · Forward {formatMoney(cash.forward_amount, payment.currency)}</p> : null}
              </article>;
            })}
          </div>
          <div className="hidden overflow-x-auto md:block">
            <Table>
              <TableHeader><TableRow><TableHead>Reference</TableHead><TableHead>Flow</TableHead><TableHead>Method / proof</TableHead><TableHead>Purpose</TableHead><TableHead>Tendered</TableHead><TableHead>Applied</TableHead><TableHead>Change / forward</TableHead><TableHead>Status</TableHead><TableHead>Recorded</TableHead></TableRow></TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow><TableCell colSpan={9} className="h-40 text-center text-muted-foreground"><Banknote className="mx-auto mb-3 h-9 w-9" />No payment transactions match the search.</TableCell></TableRow>
                ) : filtered.map((payment) => {
                  const cash = payment.cash_transaction;
                  const FlowIcon = payment.direction === "inbound" ? ArrowDownLeft : ArrowUpRight;
                  return (
                    <TableRow key={payment.id}>
                      <TableCell><p className="font-mono text-xs font-black">{cash?.cash_reference ?? payment.provider_reference ?? payment.id.slice(0, 8)}</p><p className="mt-1 text-xs text-muted-foreground">{payment.id.slice(0, 8)}</p></TableCell>
                      <TableCell><Badge variant="outline" className={payment.direction === "inbound" ? "border-emerald-500/40 text-emerald-700" : "border-amber-500/40 text-amber-700"}><FlowIcon className="mr-1 h-3.5 w-3.5" />{payment.direction === "inbound" ? "Money in" : "Money out"}</Badge></TableCell>
                      <TableCell><p className="font-bold">{paymentMethodLabel(payment.payment_method)}</p><p className="mt-1 text-xs text-muted-foreground">{payment.proof_reference ? `Proof: ${payment.proof_reference}` : payment.payment_method === "cash" ? "Physical cash" : "Proof document recorded"}</p></TableCell>
                      <TableCell className="font-bold">{titleCase(payment.purpose)}</TableCell>
                      <TableCell>{formatMoney(cash?.tendered_amount ?? payment.amount, payment.currency)}</TableCell>
                      <TableCell className="font-black">{formatMoney(cash?.applied_amount ?? payment.amount, payment.currency)}</TableCell>
                      <TableCell><p>Change: {formatMoney(cash?.change_amount ?? 0, payment.currency)}</p><p className="text-xs text-muted-foreground">Forward: {formatMoney(cash?.forward_amount ?? 0, payment.currency)}</p></TableCell>
                      <TableCell><Badge variant={payment.status === "succeeded" ? "default" : "secondary"}>{titleCase(payment.status)}</Badge></TableCell>
                      <TableCell className="text-sm text-muted-foreground">{formatDateTime(payment.completed_at ?? payment.created_at)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function paymentMethodLabel(value: string): string {
  const labels: Record<string, string> = {
    bank: "Bank",
    swipped: "Swipped",
    golink: "goLink",
    cdas: "CDAS",
    mpesa_wallet: "M-Pesa Wallet",
    mpesa_merchant: "M-Pesa Merchant",
    mpesa_agent: "M-Pesa Agent",
    ecocash_wallet: "EcoCash Wallet",
    ecocash_agent: "EcoCash Agent",
    ecocash_merchant: "EcoCash Merchant",
    cash: "Cash",
  };
  return labels[value] ?? titleCase(value);
}

function Metric({ icon: Icon, label, value, hint, tone }: { icon: typeof Banknote; label: string; value: string; hint: string; tone: "emerald" | "amber" | "blue" }) {
  const classes = tone === "emerald" ? "bg-emerald-500/12 text-emerald-700" : tone === "amber" ? "bg-amber-500/12 text-amber-700" : "bg-primary/12 text-primary";
  return <div className="loanhub-stat"><div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${classes}`}><Icon className="h-5 w-5" /></div><p className="mt-4 text-xs font-black uppercase tracking-[0.16em] text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-black">{value}</p><p className="mt-2 text-xs text-muted-foreground">{hint}</p></div>;
}
