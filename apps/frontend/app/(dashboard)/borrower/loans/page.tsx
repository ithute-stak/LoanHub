"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Banknote, CalendarDays, CheckCircle2, Clock3, Eye, HandCoins, ReceiptText, RefreshCcw } from "lucide-react";

import { listLoans } from "@/api/loans";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { PageLoader } from "@/components/ui/page-loader";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMoney, titleCase } from "@/lib/format";
import { interestMethodLabel } from "@/lib/interest-methods";
import type { Loan } from "@/types/loan";
import { toast } from "@/utils/toast";

export default function BorrowerLoansPage() {
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Loan | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setLoans(await listLoans());
    } catch (error) {
      toast.error(error, { description: "Your loans could not be loaded." });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const active = useMemo(() => loans.filter((item) => item.status === "active" || item.status === "defaulted"), [loans]);
  const totalBalance = useMemo(() => active.reduce((sum, item) => sum + Number(item.balance || 0), 0), [active]);
  const nextInstallment = useMemo(() => active.flatMap((loan) => loan.installments.map((item) => ({ loan, item }))).filter(({ item }) => !item.is_superseded && item.status !== "paid" && item.status !== "waived").sort((a, b) => new Date(a.item.due_date).getTime() - new Date(b.item.due_date).getTime())[0] ?? null, [active]);

  if (loading) return <PageLoader rows={6} />;

  return (
    <div className="loanhub-page">
      <section className="loanhub-hero flex flex-col justify-between gap-5 p-6 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.24em] text-primary">Borrower loan book</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">My loans and repayment schedule</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">The lending company records the approved disbursement method. Repayments may be made through any recognised channel, with proof supplied for non-cash methods, using your official loan number.</p>
        </div>
        <Button variant="outline" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Refresh</Button>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <Metric icon={HandCoins} label="Active loans" value={String(active.length)} hint="Loans currently accepting repayments" />
        <Metric icon={Banknote} label="Outstanding balance" value={formatMoney(totalBalance)} hint="Total amount still due" />
        <Metric icon={CalendarDays} label="Next due amount" value={nextInstallment ? formatMoney(Number(nextInstallment.item.total_due) - Number(nextInstallment.item.paid_amount)) : formatMoney(0)} hint={nextInstallment ? `Due ${formatDate(nextInstallment.item.due_date)}` : "No unpaid instalment"} />
      </div>

      <Alert>
        <ReceiptText className="h-4 w-4" />
        <AlertTitle>How to repay</AlertTitle>
        <AlertDescription>Take your loan number and payment proof to the responsible company payment desk. Staff will show any partial balance, cash change, or forward amount before issuing a receipt.</AlertDescription>
      </Alert>

      <div className="grid gap-5 lg:grid-cols-2">
        {loans.length === 0 ? <Card className="loanhub-panel lg:col-span-2"><CardContent className="flex min-h-72 flex-col items-center justify-center p-8 text-center"><HandCoins className="h-12 w-12 text-muted-foreground" /><h2 className="mt-4 text-xl font-black">No loans yet</h2><p className="mt-2 max-w-xl text-sm text-muted-foreground">When you accept a loan offer or a company approves an internal application, the loan and its unique number will appear here.</p></CardContent></Card> : loans.map((loan) => {
          const progress = Number(loan.total_repayable) > 0 ? (Number(loan.amount_paid) / Number(loan.total_repayable)) * 100 : 0;
          const current = loan.installments.find((item) => !item.is_superseded && item.status !== "paid" && item.status !== "waived") ?? null;
          return <Card key={loan.id} className="loanhub-panel overflow-hidden">
            <CardHeader className="border-b bg-gradient-to-br from-primary/8 to-emerald-500/8">
              <div className="flex items-start justify-between gap-4"><div><p className="font-mono text-xs font-black text-primary">{loan.loan_reference}</p><CardTitle className="mt-2">{formatMoney(loan.principal_amount)} loan</CardTitle><CardDescription>{interestMethodLabel(loan.calculation_method)} · {loan.repayment_period} months</CardDescription></div><Badge variant={loan.status === "active" || loan.status === "completed" ? "default" : "secondary"}>{titleCase(loan.status)}</Badge></div>
            </CardHeader>
            <CardContent className="space-y-5 p-5">
              <div className="grid grid-cols-2 gap-3"><Value label="Monthly instalment" value={formatMoney(loan.installment_amount)} emphasis /><Value label="Balance" value={formatMoney(loan.balance)} /><Value label="Paid" value={formatMoney(loan.amount_paid)} /><Value label="Total repayable" value={formatMoney(loan.total_repayable)} /></div>
              <div><div className="mb-2 flex justify-between text-xs font-bold"><span>Repayment progress</span><span>{progress.toFixed(1)}%</span></div><Progress value={Math.min(100, Math.max(0, progress))} /></div>
              {loan.renewal_cycle_count > 0 && <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4"><p className="text-xs font-black uppercase tracking-[0.12em] text-primary">Maturity renewal cycle {loan.renewal_cycle_count}</p><p className="mt-1 text-sm font-bold">Original maturity {loan.original_maturity_date ? formatDate(loan.original_maturity_date) : "—"}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">The remaining eligible balance was recalculated into the current schedule. Open the full schedule to see the renewal history.</p></div>}
              {current ? <div className="rounded-2xl border bg-muted/30 p-4"><p className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">Current instalment {current.installment_number}</p><p className="mt-1 text-lg font-black">{formatMoney(Math.max(0, Number(current.total_due) - Number(current.paid_amount)))}</p><p className="mt-1 text-xs text-muted-foreground">Due {formatDate(current.due_date)}</p></div> : <div className="rounded-2xl border bg-emerald-500/10 p-4 text-emerald-700"><p className="flex items-center gap-2 font-black"><CheckCircle2 className="h-4 w-4" />All scheduled instalments cleared</p></div>}
              <Button variant="outline" className="h-12 w-full rounded-xl" onClick={() => setSelected(loan)}><Eye className="h-4 w-4" />View full schedule</Button>
            </CardContent>
          </Card>;
        })}
      </div>

      <CustomDialog
        open={Boolean(selected)}
        onOpenChange={(open) => !open && setSelected(null)}
        title="Loan instalment schedule"
        description={selected ? `${selected.loan_reference} · Bring this loan number when making any repayment.` : undefined}
        contentClassName="sm:max-w-4xl"
      >
        <div className="space-y-5 p-6 sm:p-8">
          {selected && <div className="space-y-5"><div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><Value label="Principal" value={formatMoney(selected.principal_amount)} /><Value label="Total repayable" value={formatMoney(selected.total_repayable)} /><Value label="Paid" value={formatMoney(selected.amount_paid)} /><Value label="Balance" value={formatMoney(selected.balance)} emphasis /></div>{selected.renewal_cycles.length > 0 && <div className="space-y-3 rounded-3xl border border-primary/20 bg-primary/5 p-4"><div><p className="text-sm font-black text-primary">Maturity renewal history</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Each cycle remains attached to the original loan; no fake cash disbursement is created.</p></div><div className="grid gap-2 sm:grid-cols-2">{selected.renewal_cycles.map((cycle) => <div key={cycle.id} className="rounded-2xl border bg-background p-3"><div className="flex items-center justify-between gap-2"><p className="font-black">Cycle {cycle.cycle_number}</p><Badge variant="secondary">{titleCase(cycle.status)}</Badge></div><p className="mt-2 text-sm font-black">{formatMoney(cycle.opening_balance)} → {formatMoney(cycle.total_repayable)}</p><p className="mt-1 text-xs text-muted-foreground">{cycle.term_months} months · {formatMoney(cycle.installment_amount)} instalment · matures {formatDate(cycle.maturity_date)}</p></div>)}</div></div>}<div className="space-y-3 md:hidden">{selected.installments.filter((item) => !item.is_superseded).map((item) => <article key={item.id} className="rounded-2xl border bg-card p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">Instalment {item.installment_number}</p><p className="mt-1 text-lg font-black">{formatMoney(Math.max(0, Number(item.total_due) - Number(item.paid_amount)))}</p><p className="mt-1 text-xs text-muted-foreground">Due {formatDate(item.due_date)}</p></div><Badge variant={item.status === "paid" ? "default" : "secondary"}>{titleCase(item.status)}</Badge></div><div className="mt-3 grid grid-cols-2 gap-2 text-xs"><Value label="Expected" value={formatMoney(item.total_due)} /><Value label="Paid" value={formatMoney(item.paid_amount)} /></div></article>)}</div><div className="hidden overflow-x-auto rounded-2xl border md:block"><Table><TableHeader><TableRow><TableHead>#</TableHead><TableHead>Due</TableHead><TableHead>Expected</TableHead><TableHead>Paid</TableHead><TableHead>Remaining</TableHead><TableHead>Status</TableHead></TableRow></TableHeader><TableBody>{selected.installments.filter((item) => !item.is_superseded).map((item) => <TableRow key={item.id}><TableCell className="font-black">{item.installment_number}</TableCell><TableCell>{formatDate(item.due_date)}</TableCell><TableCell>{formatMoney(item.total_due)}</TableCell><TableCell>{formatMoney(item.paid_amount)}</TableCell><TableCell className="font-black">{formatMoney(Math.max(0, Number(item.total_due) - Number(item.paid_amount)))}</TableCell><TableCell><Badge variant={item.status === "paid" ? "default" : "secondary"}>{titleCase(item.status)}</Badge></TableCell></TableRow>)}</TableBody></Table></div>{selected.installments.some((item) => item.is_superseded) && <div className="rounded-2xl border bg-muted/30 p-4 text-xs leading-5 text-muted-foreground">{selected.installments.filter((item) => item.is_superseded).length} historical unpaid instalment(s) were superseded by a maturity renewal. Their original values are preserved in the renewal-cycle audit snapshot.</div>}<Alert><Clock3 className="h-4 w-4" /><AlertTitle>Partial and advance payments</AlertTitle><AlertDescription>A partial payment leaves the current instalment balance open. An advance payment can be carried forward to future instalments, while cash change is excluded from the amount posted to the loan.</AlertDescription></Alert></div>}
          <DialogFooter className="mx-0 mb-0"><Button onClick={() => setSelected(null)}>Close</Button></DialogFooter>
        </div>
      </CustomDialog>
    </div>
  );
}

function Metric({ icon: Icon, label, value, hint }: { icon: typeof HandCoins; label: string; value: string; hint: string }) { return <div className="loanhub-stat"><div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/12 text-primary"><Icon className="h-5 w-5" /></div><p className="mt-4 text-xs font-black uppercase tracking-[0.16em] text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-black">{value}</p><p className="mt-2 text-xs text-muted-foreground">{hint}</p></div>; }
function Value({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) { return <div className="rounded-2xl border bg-background/70 p-3"><p className="text-[11px] font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p><p className={`mt-1 font-black ${emphasis ? "text-lg text-primary" : "text-sm"}`}>{value}</p></div>; }
