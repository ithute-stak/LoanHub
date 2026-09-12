"use client";

import { useMemo, useState, type ReactNode } from "react";
import { BookOpenCheck, FilePlus2, Landmark, Plus, Scale, Trash2 } from "lucide-react";

import { createJournalEntry, postJournalEntry } from "@/api/accounting";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DataPagination } from "@/components/ui/data-pagination";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatMoney, titleCase } from "@/lib/format";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { upsertJournal } from "@/store/features/slices/financialOperationsSlice";
import type { FinancialStatement, JournalEntry } from "@/types/accounting";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const PAGE_SIZE = 12;

type DraftLine = { account_id: string; description: string; debit: number; credit: number };

export function AccountingBooksPanel({ businessDate, branchId, onRefresh }: { businessDate: string; branchId: string | null; onRefresh: () => Promise<void> | void }) {
  const dispatch = useAppDispatch();
  const { accounts, journals, trialBalance, profitAndLoss, balanceSheet } = useAppSelector((state) => state.financialOperations);
  const [journalOpen, setJournalOpen] = useState(false);
  const [working, setWorking] = useState(false);
  const [description, setDescription] = useState("");
  const [reference, setReference] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([
    { account_id: accounts[0]?.id ?? "", description: "", debit: 0, credit: 0 },
    { account_id: accounts[1]?.id ?? "", description: "", debit: 0, credit: 0 },
  ]);
  const [journalPage, setJournalPage] = useState(1);
  const [trialPage, setTrialPage] = useState(1);

  const totals = useMemo(() => lines.reduce((acc, line) => ({ debit: acc.debit + Number(line.debit || 0), credit: acc.credit + Number(line.credit || 0) }), { debit: 0, credit: 0 }), [lines]);
  const balanced = totals.debit > 0 && Math.abs(totals.debit - totals.credit) < 0.005;
  const pagedJournals = journals.slice((journalPage - 1) * PAGE_SIZE, journalPage * PAGE_SIZE);
  const trialLines = trialBalance?.lines ?? [];
  const pagedTrial = trialLines.slice((trialPage - 1) * PAGE_SIZE, trialPage * PAGE_SIZE);

  function openJournal() {
    setDescription("");
    setReference("");
    setLines([
      { account_id: accounts[0]?.id ?? "", description: "", debit: 0, credit: 0 },
      { account_id: accounts[1]?.id ?? "", description: "", debit: 0, credit: 0 },
    ]);
    setJournalOpen(true);
  }

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((current) => current.map((line, lineIndex) => lineIndex === index ? { ...line, ...patch } : line));
  }

  async function saveJournal() {
    if (!description.trim() || !balanced || lines.some((line) => !line.account_id)) {
      toast.error("Complete the journal and make total debit equal total credit");
      return;
    }
    setWorking(true);
    try {
      const created = await createJournalEntry({
        entry_date: businessDate,
        branch_id: branchId,
        description: description.trim(),
        reference_type: "manual_adjustment",
        reference_id: reference.trim() || null,
        lines: lines.filter((line) => Number(line.debit || 0) > 0 || Number(line.credit || 0) > 0),
      });
      dispatch(upsertJournal(created));
      setJournalOpen(false);
      toast.success("Balanced draft journal created");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The journal could not be created"));
    } finally {
      setWorking(false);
    }
  }

  async function post(entry: JournalEntry) {
    setWorking(true);
    try {
      const posted = await postJournalEntry(entry.id);
      dispatch(upsertJournal(posted));
      await onRefresh();
      toast.success("Journal posted to the official ledger");
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "The journal could not be posted"));
    } finally {
      setWorking(false);
    }
  }

  const netProfit = Number(profitAndLoss?.totals.net_profit ?? 0);
  const assets = Number(balanceSheet?.totals.asset ?? 0);
  const liabilities = Number(balanceSheet?.totals.liability ?? 0);
  const equity = Number(balanceSheet?.totals.equity ?? 0);

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <BookMetric label="Net profit" value={formatMoney(netProfit)} hint="Income less posted expenses" />
        <BookMetric label="Assets" value={formatMoney(assets)} hint="Cash, loans and receivables" />
        <BookMetric label="Liabilities" value={formatMoney(liabilities)} hint="Amounts the company owes" />
        <BookMetric label="Owner equity" value={formatMoney(equity)} hint="Capital and retained position" />
      </div>

      <Card className="rounded-3xl border-primary/20 bg-gradient-to-br from-primary/10 via-card to-emerald-500/5">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div><CardTitle className="flex items-center gap-2"><Landmark className="h-5 w-5 text-primary" />Official accounting books</CardTitle><CardDescription>Normal loan, repayment, opening-balance and expense movements post automatically. Manual journals are reserved for authorised adjustments.</CardDescription></div>
          <Button onClick={openJournal}><FilePlus2 className="h-4 w-4" />Manual journal</Button>
        </CardHeader>
      </Card>

      <Tabs defaultValue="profit-loss" className="space-y-4">
        <TabsList className="h-auto flex-wrap justify-start rounded-2xl p-1">
          <TabsTrigger value="profit-loss">Profit & loss</TabsTrigger>
          <TabsTrigger value="balance-sheet">Balance sheet</TabsTrigger>
          <TabsTrigger value="trial">Trial balance</TabsTrigger>
          <TabsTrigger value="journals">General journal</TabsTrigger>
        </TabsList>
        <TabsContent value="profit-loss"><StatementCard title="Profit and loss" description="Revenue, expenses and the resulting profit for the selected period." statement={profitAndLoss} /></TabsContent>
        <TabsContent value="balance-sheet"><StatementCard title="Balance sheet" description="Assets, liabilities and equity as at the selected date." statement={balanceSheet} /></TabsContent>
        <TabsContent value="trial">
          <Card className="overflow-hidden rounded-3xl"><CardHeader><CardTitle className="flex items-center gap-2"><Scale className="h-5 w-5 text-primary" />Trial balance</CardTitle><CardDescription>Total posted debit must equal total posted credit.</CardDescription></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Account</TableHead><TableHead>Type</TableHead><TableHead className="text-right">Debit</TableHead><TableHead className="text-right">Credit</TableHead><TableHead className="text-right">Balance</TableHead></TableRow></TableHeader><TableBody>{pagedTrial.map((line) => <TableRow key={line.account_id}><TableCell><span className="font-mono text-xs font-black text-primary">{line.code}</span><p className="font-semibold">{line.name}</p></TableCell><TableCell><Badge variant="outline">{titleCase(line.account_type)}</Badge></TableCell><TableCell className="text-right">{formatMoney(line.debit)}</TableCell><TableCell className="text-right">{formatMoney(line.credit)}</TableCell><TableCell className="text-right font-black">{formatMoney(line.balance)}</TableCell></TableRow>)}</TableBody></Table></div><DataPagination page={trialPage} pageSize={PAGE_SIZE} total={trialLines.length} onPageChange={setTrialPage} /></CardContent></Card>
        </TabsContent>
        <TabsContent value="journals">
          <Card className="overflow-hidden rounded-3xl"><CardHeader><CardTitle>General journal</CardTitle><CardDescription>Automatic and manual balanced entries, with source references and posting status.</CardDescription></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Entry</TableHead><TableHead>Description</TableHead><TableHead>Source</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Value</TableHead><TableHead className="text-right">Action</TableHead></TableRow></TableHeader><TableBody>{pagedJournals.map((entry) => <TableRow key={entry.id}><TableCell><p className="font-mono text-xs font-black text-primary">{entry.entry_number}</p><p className="text-xs text-muted-foreground">{entry.entry_date}</p></TableCell><TableCell className="max-w-sm"><p className="font-semibold">{entry.description}</p></TableCell><TableCell className="text-xs">{entry.reference_type ? titleCase(entry.reference_type) : "Manual"}<p className="font-mono text-muted-foreground">{entry.reference_id ?? "—"}</p></TableCell><TableCell><Badge variant={entry.status === "posted" ? "default" : "secondary"}>{titleCase(entry.status)}</Badge></TableCell><TableCell className="text-right font-black">{formatMoney(entry.total_debit)}</TableCell><TableCell className="text-right">{entry.status === "draft" ? <LoadingButton size="sm" loading={working} onClick={() => void post(entry)}><BookOpenCheck className="h-4 w-4" />Post</LoadingButton> : "—"}</TableCell></TableRow>)}</TableBody></Table></div><DataPagination page={journalPage} pageSize={PAGE_SIZE} total={journals.length} onPageChange={setJournalPage} /></CardContent></Card>
        </TabsContent>
      </Tabs>

      <CustomDialog open={journalOpen} onOpenChange={(open) => !working && setJournalOpen(open)} title="Create balanced journal" description="Use this only for a documented adjustment that was not created automatically by a LoanHub transaction." contentClassName="sm:max-w-5xl">
        <div className="space-y-5 p-6 sm:p-8">
          <div className="grid gap-4 sm:grid-cols-2"><Field label="Journal date"><Input type="date" value={businessDate} disabled /></Field><Field label="Supporting reference"><Input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Voucher, bank reference or correction number" /></Field><div className="sm:col-span-2"><Field label="Description"><Textarea required value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Explain why the adjustment is required" /></Field></div></div>
          <div className="overflow-x-auto rounded-2xl border"><Table><TableHeader><TableRow><TableHead>Account</TableHead><TableHead>Description</TableHead><TableHead className="w-36">Debit</TableHead><TableHead className="w-36">Credit</TableHead><TableHead className="w-14" /></TableRow></TableHeader><TableBody>{lines.map((line, index) => <TableRow key={`${index}-${line.account_id}`}><TableCell><Select value={line.account_id || "none"} onValueChange={(account_id) => updateLine(index, { account_id: account_id === "none" ? "" : account_id })}><SelectTrigger className="min-w-64"><SelectValue placeholder="Select account" /></SelectTrigger><SelectContent><SelectItem value="none" disabled>Select account</SelectItem>{accounts.map((account) => <SelectItem key={account.id} value={account.id}>{account.code} · {account.name}</SelectItem>)}</SelectContent></Select></TableCell><TableCell><Input value={line.description} onChange={(event) => updateLine(index, { description: event.target.value })} /></TableCell><TableCell><Input type="number" min={0} step="0.01" value={line.debit || ""} onChange={(event) => updateLine(index, { debit: Number(event.target.value || 0), credit: event.target.value ? 0 : line.credit })} /></TableCell><TableCell><Input type="number" min={0} step="0.01" value={line.credit || ""} onChange={(event) => updateLine(index, { credit: Number(event.target.value || 0), debit: event.target.value ? 0 : line.debit })} /></TableCell><TableCell><Button type="button" size="icon" variant="ghost" disabled={lines.length <= 2} onClick={() => setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))}><Trash2 className="h-4 w-4" /></Button></TableCell></TableRow>)}</TableBody></Table></div>
          <Button type="button" variant="outline" onClick={() => setLines((current) => [...current, { account_id: accounts[0]?.id ?? "", description: "", debit: 0, credit: 0 }])}><Plus className="h-4 w-4" />Add journal line</Button>
          <div className={`grid gap-3 rounded-2xl border p-4 sm:grid-cols-3 ${balanced ? "border-emerald-500/40 bg-emerald-500/5" : "border-amber-500/40 bg-amber-500/5"}`}><BookMetric label="Total debit" value={formatMoney(totals.debit)} hint="" /><BookMetric label="Total credit" value={formatMoney(totals.credit)} hint="" /><BookMetric label="Difference" value={formatMoney(Math.abs(totals.debit - totals.credit))} hint={balanced ? "Balanced" : "Must be zero"} /></div>
          <DialogFooter className="mx-0 mb-0"><Button type="button" variant="outline" onClick={() => setJournalOpen(false)} disabled={working}>Cancel</Button><LoadingButton loading={working} disabled={!balanced || !description.trim()} onClick={() => void saveJournal()} loadingText="Saving journal…">Save draft journal</LoadingButton></DialogFooter>
        </div>
      </CustomDialog>
    </div>
  );
}

function StatementCard({ title, description, statement }: { title: string; description: string; statement: FinancialStatement | null }) {
  const sections = Object.entries(statement?.sections ?? {});
  return <Card className="rounded-3xl"><CardHeader><CardTitle>{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader><CardContent className="space-y-5">{sections.length === 0 ? <p className="py-10 text-center text-muted-foreground">No posted accounting activity for this period.</p> : sections.map(([name, rows]) => <div key={name} className="overflow-hidden rounded-2xl border"><div className="flex items-center justify-between bg-muted/30 px-4 py-3"><p className="font-black">{titleCase(name)}</p><p className="font-black">{formatMoney(statement?.totals[name] ?? 0)}</p></div><Table><TableBody>{rows.map((row) => <TableRow key={`${name}-${row.code}`}><TableCell><span className="font-mono text-xs text-primary">{row.code}</span> · {row.name}</TableCell><TableCell className="text-right font-black">{formatMoney(row.amount)}</TableCell></TableRow>)}</TableBody></Table></div>)}</CardContent></Card>;
}

function BookMetric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return <div className="rounded-2xl border bg-card p-4"><p className="text-xs font-black uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-2 text-xl font-black">{value}</p>{hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}</div>;
}
function Field({ label, children }: { label: string; children: ReactNode }) { return <div className="space-y-2"><Label>{label}</Label>{children}</div>; }
