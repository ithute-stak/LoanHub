"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { ArrowDownLeft, ArrowUpRight, BookOpen, CalendarDays, HandCoins, ReceiptText, RefreshCcw, Wallet } from "lucide-react";
import { listJournalEntries } from "@/api/accounting";
import { listLoans } from "@/api/loans";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { JournalEntry } from "@/types/accounting";
import type { Loan } from "@/types/loan";
import { toast } from "@/utils/toast";
import { getErrorMessage } from "@/utils/apiError";

type Period = "day" | "week" | "month" | "year";
const CATEGORIES = ["Airtime", "Water", "Electricity", "Transport", "Stationery", "Rent", "Maintenance", "Other"];
function localDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function periodStart(period: Period, today: Date) {
  const first = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (period === "week") first.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  if (period === "month") first.setDate(1);
  if (period === "year") { first.setMonth(0); first.setDate(1); }
  return localDate(first);
}
export default function FinanceDeskPage() {
  const [period, setPeriod] = useState<Period>("day");
  const [asOf, setAsOf] = useState(() => localDate(new Date()));
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [category, setCategory] = useState("Airtime");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const rangeStart = useMemo(() => {
    const [year, month, day] = asOf.split("-").map(Number);
    return periodStart(period, new Date(year, month - 1, day));
  }, [period, asOf]);
  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [journal, currentLoans] = await Promise.all([
        listJournalEntries({ fromDate: rangeStart, toDate: asOf, limit: 1000 }),
        listLoans(),
      ]);
      setEntries(journal);
      setLoans(currentLoans);
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Could not load daily finance activity"));
    } finally {
      setLoading(false);
    }
  }, [rangeStart, asOf]);
  useEffect(() => { void reload(); }, [reload]);

  const expenses = useMemo(() => entries.filter(e => e.reference_type === "expense" && e.status === "posted"), [entries]);
  const expenseTotal = expenses.reduce((total, e) => total + Number(e.total_debit), 0);
  const disbursements = useMemo(() => loans.filter(l => l.disbursed_at && l.disbursed_at.slice(0, 10) >= rangeStart && l.disbursed_at.slice(0, 10) <= asOf), [loans, rangeStart, asOf]);
  const issuedTotal = disbursements.reduce((total, l) => total + Number(l.principal_amount), 0);
  const journalReceipts = entries.filter(e => e.status === "posted" && ["loan_repayment", "repayment"].includes(e.reference_type ?? ""));
  async function saveExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) { toast.error("Enter a valid positive expense amount."); return; }
    setSaving(true);
    try {
      await api.post("/accounting/expenses", {
        amount: parsed,
        description: `${category}: ${description.trim()}`,
        expense_account_code: "6500",
        paid_now: true,
        entry_date: asOf,
        external_reference: reference.trim() || undefined,
      });
      toast.success("Expense posted to accounting");
      setAmount(""); setDescription(""); setReference("");
      await reload();
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Expense could not be recorded"));
    } finally { setSaving(false); }
  }
  return <div className="space-y-6 p-2 sm:p-0">
    <div className="rounded-3xl border bg-gradient-to-br from-primary/10 via-background to-background p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><p className="text-xs font-bold uppercase tracking-widest text-primary">Payments & Finance</p><h1 className="mt-2 text-3xl font-black">Daily Finance Desk</h1><p className="mt-2 text-sm text-muted-foreground">Record expenses and see live accounting and loan activity without navigating the full financial books.</p></div>
        <Button variant="outline" onClick={() => void reload()} disabled={loading}><RefreshCcw className="mr-2 h-4 w-4"/>Refresh</Button>
      </div>
      <div className="mt-5 flex flex-wrap items-end gap-3">
        <div className="space-y-1"><Label htmlFor="finance-date">Through date</Label><Input id="finance-date" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} max={localDate(new Date())}/></div>
        <div className="flex flex-wrap gap-1 rounded-xl border p-1">{(["day","week","month","year"] as Period[]).map(p => <Button key={p} type="button" size="sm" variant={period === p ? "default" : "ghost"} onClick={() => setPeriod(p)}>{({day:"Day",week:"Week",month:"Month",year:"Year"})[p]}</Button>)}</div>
        <p className="pb-2 text-xs text-muted-foreground">Showing {rangeStart} to {asOf}</p>
      </div>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric icon={<HandCoins className="h-5 w-5"/>} title="Loans issued" amount={issuedTotal} hint={`${disbursements.length} disbursed loans`}/>
      <Metric icon={<ReceiptText className="h-5 w-5"/>} title="Recorded expenses" amount={expenseTotal} hint={`${expenses.length} posted expenses`}/>
      <Metric icon={<ArrowDownLeft className="h-5 w-5"/>} title="Repayment journals" amount={journalReceipts.reduce((sum, e) => sum + Number(e.total_debit), 0)} hint="Identified journals only; confirm with payment register"/>
      <Metric icon={<Wallet className="h-5 w-5"/>} title="Cash closing" amount={null} hint="Requires verified opening and closing counts"/>
    </div>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card className="rounded-2xl"><CardHeader><CardTitle>Record a daily cash expense</CardTitle><p className="text-sm text-muted-foreground">Creates a posted expense journal using LoanHub's existing accounting service. Cash expenses only; use the accounting workspace for other payment methods.</p></CardHeader>
        <CardContent><form className="space-y-4" onSubmit={saveExpense}>
          <div className="space-y-1"><Label htmlFor="expense-category">Category</Label><select id="expense-category" className="h-10 w-full rounded-lg border bg-background px-3" value={category} onChange={e => setCategory(e.target.value)}>{CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}</select></div>
          <div className="space-y-1"><Label htmlFor="expense-amount">Amount (LSL)</Label><Input id="expense-amount" type="number" step="0.01" min="0.01" required value={amount} onChange={e => setAmount(e.target.value)} placeholder="0.00"/></div>
          <div className="space-y-1"><Label htmlFor="expense-description">What was purchased?</Label><Textarea id="expense-description" minLength={2} required value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe the expense and supplier"/></div>
          <div className="space-y-1"><Label htmlFor="expense-reference">Receipt / document reference (optional)</Label><Input id="expense-reference" value={reference} onChange={e => setReference(e.target.value)} placeholder="Receipt number"/></div>
          <Button disabled={saving || loading} type="submit" className="w-full">{saving ? "Recording expense..." : "Post cash expense"}</Button>
        </form></CardContent>
      </Card>
      <Card className="rounded-2xl"><CardHeader><CardTitle>Recent expense entries</CardTitle><p className="text-sm text-muted-foreground">Posted entries from the selected period; full audit details remain in Financial Books.</p></CardHeader><CardContent className="space-y-2">
        {loading ? <p className="text-sm text-muted-foreground">Loading activity…</p> : expenses.length === 0 ? <p className="rounded-xl border p-5 text-sm text-muted-foreground">No posted expenses in the selected period.</p> : expenses.slice(0, 15).map(e => <div key={e.id} className="flex items-center justify-between gap-3 rounded-xl border p-3"><div className="min-w-0"><p className="truncate text-sm font-semibold">{e.description}</p><p className="text-xs text-muted-foreground">{e.entry_date} · {e.entry_number}</p></div><strong className="shrink-0">{formatMoney(e.total_debit)}</strong></div>)}
      </CardContent></Card>
    </div>
    <div className="grid gap-3 md:grid-cols-3">
      <Action href="/company/payments" icon={<ArrowDownLeft className="h-5 w-5"/>} title="Record client repayments" description="Use LoanHub's payment register and verified receipt posting."/>
      <Action href="/company/loans" icon={<ArrowUpRight className="h-5 w-5"/>} title="View loans & disbursements" description="Review every client loan and detailed disbursement records."/>
      <Action href="/company/accounting" icon={<BookOpen className="h-5 w-5"/>} title="Financial books" description="Open the full accounting journals, trial balance and statements."/>
    </div>
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm"><CalendarDays className="mr-2 inline h-4 w-4"/>Cash opening/closing confirmation and legacy folio receipts require a reconciled backend workflow. They are not simulated here or mixed with real cash totals.</div>
  </div>;
}
function Metric({icon,title,amount,hint}:{icon:ReactNode;title:string;amount:number|null;hint:string}) {
  return <Card className="rounded-2xl"><CardContent className="space-y-2 p-5"><div className="flex items-center gap-2 text-sm text-muted-foreground">{icon}{title}</div><p className="text-2xl font-black">{amount === null ? "Not yet available" : formatMoney(amount)}</p><p className="text-xs text-muted-foreground">{hint}</p></CardContent></Card>;
}
function Action({href,icon,title,description}:{href:string;icon:ReactNode;title:string;description:string}) {
  return <Link href={href} className="flex gap-3 rounded-2xl border p-5 transition hover:border-primary/40 hover:bg-primary/5">{icon}<div><p className="font-bold">{title}</p><p className="mt-1 text-xs text-muted-foreground">{description}</p></div></Link>;
}
