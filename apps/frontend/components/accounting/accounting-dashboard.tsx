"use client";


import {Input} from "@/components/ui/input";
import {Textarea} from "@/components/ui/textarea";
import {NativeSelect} from "@/components/ui/native-select";
import {
    BookOpenCheck,
    Landmark,
    Loader2,
    Plus,
    RefreshCcw,
    Scale,
} from "lucide-react";
import {useCallback, useEffect, useRef, useState} from "react";
import {toast} from "@/utils/toast";

import {
    createJournalEntry,
    getBalanceSheet,
    getProfitAndLoss,
    getTrialBalance,
    listAccountingAccounts,
    listJournalEntries,
    postJournalEntry,
} from "@/api/accounting";
import {IthutePoweredBy} from "@/components/brand/ithute-brand";
import {formatMoney} from "@/lib/format";
import {useAppData} from "@/provider/appDataProvider";
import type {
    AccountingAccount,
    FinancialStatement,
    JournalEntry,
    TrialBalance,
} from "@/types/accounting";
import {getErrorMessage} from "@/utils/apiError";

export function AccountingDashboard({mode}: { mode: "company" | "superadmin" }) {
    const {companies, currentCompany} = useAppData();
    const [companyId, setCompanyId] = useState(mode === "company" ? currentCompany?.id ?? "" : "");
    const [accounts, setAccounts] = useState<AccountingAccount[]>([]);
    const [entries, setEntries] = useState<JournalEntry[]>([]);
    const [trial, setTrial] = useState<TrialBalance | null>(null);
    const [profitLoss, setProfitLoss] = useState<FinancialStatement | null>(null);
    const [balanceSheet, setBalanceSheet] = useState<FinancialStatement | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [description, setDescription] = useState("");
    const [amount, setAmount] = useState("");
    const [debitAccount, setDebitAccount] = useState("");
    const [creditAccount, setCreditAccount] = useState("");
    const activeLoadRef = useRef<string | null>(null);
    const loadSequenceRef = useRef(0);

    useEffect(() => {
        if (mode !== "company" || !currentCompany?.id) return;
        const timer = window.setTimeout(() => setCompanyId(currentCompany.id), 0);
        return () => window.clearTimeout(timer);
    }, [currentCompany?.id, mode]);

    const selectedCompanyId = mode === "superadmin" ? companyId || undefined : companyId;

    const load = useCallback(async () => {
        const scopeKey = selectedCompanyId ?? "platform";

        // React Strict Mode can run the mount effect twice in development.
        // Ignore the duplicate request while the same ledger scope is loading.
        if (activeLoadRef.current === scopeKey) return;

        activeLoadRef.current = scopeKey;
        const sequence = ++loadSequenceRef.current;
        setLoading(true);

        try {
            // GET /accounting/accounts already ensures that the chart exists.
            // A separate bootstrap POST here caused two concurrent inserts.
            const accountItems = await listAccountingAccounts(selectedCompanyId);
            const [entryItems, trialData, profitData, balanceData] = await Promise.all([
                listJournalEntries({companyId: selectedCompanyId}),
                getTrialBalance({companyId: selectedCompanyId}),
                getProfitAndLoss({companyId: selectedCompanyId}),
                getBalanceSheet({companyId: selectedCompanyId}),
            ]);

            if (sequence !== loadSequenceRef.current) return;

            setAccounts(accountItems);
            setEntries(entryItems);
            setTrial(trialData);
            setProfitLoss(profitData);
            setBalanceSheet(balanceData);
            setDebitAccount((current) => current || accountItems[0]?.id || "");
            setCreditAccount((current) => current || accountItems[1]?.id || "");
        } catch (error: unknown) {
            if (sequence === loadSequenceRef.current) {
                toast.error(getErrorMessage(error, "Could not load accounting records"));
            }
        } finally {
            if (sequence === loadSequenceRef.current) {
                activeLoadRef.current = null;
                setLoading(false);
            }
        }
    }, [selectedCompanyId]);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    async function addEntry() {
        const numericAmount = Number(amount);
        if (!description.trim() || !debitAccount || !creditAccount || numericAmount <= 0) {
            toast.error("Complete the description, amount and both accounts");
            return;
        }
        if (debitAccount === creditAccount) {
            toast.error("Debit and credit accounts must be different");
            return;
        }
        setSubmitting(true);
        try {
            const entry = await createJournalEntry({
                entry_date: new Date().toISOString().slice(0, 10),
                description: description.trim(),
                lines: [
                    {account_id: debitAccount, debit: numericAmount, credit: 0},
                    {account_id: creditAccount, debit: 0, credit: numericAmount},
                ],
            }, selectedCompanyId);
            setEntries((current) => [entry, ...current]);
            setDescription("");
            setAmount("");
            toast.success("Balanced journal entry created");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Journal entry could not be created"));
        } finally {
            setSubmitting(false);
        }
    }

    const netProfit = Number(profitLoss?.totals.net_profit ?? 0);
    const assets = Number(balanceSheet?.totals.asset ?? 0);
    const liabilities = Number(balanceSheet?.totals.liability ?? 0);

    return (
        <main className="space-y-6">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-primary/10 blur-3xl"/>
                <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-primary"><Landmark className="h-5 w-5"/><span
                            className="text-xs font-black uppercase tracking-[0.16em]">Double-entry accounting</span>
                        </div>
                        <h1 className="mt-2 text-3xl font-black">Accounting and general ledger</h1><p
                        className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Maintain a chart of accounts,
                        balanced journals, trial balance, profit and loss, and balance sheet records.</p></div>
                    <div className="flex items-center gap-3"><IthutePoweredBy/>
                        <button type="button" onClick={() => void load()} className="rounded-xl border p-2.5">
                            <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}/></button>
                    </div>
                </div>
            </section>

            {mode === "superadmin" && (
                <section className="rounded-2xl border bg-card p-4"><label className="block max-w-md"><span
                    className="mb-2 block text-sm font-black">Ledger scope</span><NativeSelect value={companyId}
                                                                                               onChange={(event) => setCompanyId(event.target.value)}
                                                                                               className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold">
                    <option value="">LoanHub platform ledger</option>
                    {companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
                </NativeSelect></label></section>
            )}

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric label="Net profit" value={formatMoney(netProfit)}/>
                <Metric label="Total assets" value={formatMoney(assets)}/>
                <Metric label="Total liabilities" value={formatMoney(liabilities)}/>
                <Metric label="Posted journal value"
                        value={formatMoney(entries.filter((entry) => entry.status === "posted").reduce((sum, entry) => sum + Number(entry.total_debit), 0))}/>
            </section>

            <section className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
                <article className="rounded-3xl border bg-card p-5 shadow-sm">
                    <div className="flex items-center gap-2"><Plus className="h-5 w-5 text-primary"/><h2
                        className="text-lg font-black">New journal entry</h2></div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">Create a balanced two-line entry. It
                        remains draft until posted.</p>
                    <div className="mt-5 space-y-3"><Textarea value={description}
                                                              onChange={(event) => setDescription(event.target.value)}
                                                              rows={3} placeholder="Entry description"
                                                              className="w-full rounded-xl border bg-background p-3 text-sm"/><Input
                        type="number" min="0.01" step="0.01" value={amount}
                        onChange={(event) => setAmount(event.target.value)} placeholder="Amount (LSL)"
                        className="h-11 w-full rounded-xl border bg-background px-3 text-sm"/><label><span
                        className="mb-1 block text-xs font-bold">Debit account</span><NativeSelect value={debitAccount}
                                                                                                   onChange={(event) => setDebitAccount(event.target.value)}
                                                                                                   className="h-11 w-full rounded-xl border bg-background px-3 text-sm">{accounts.map((account) =>
                        <option key={account.id}
                                value={account.id}>{account.code} · {account.name}</option>)}</NativeSelect></label><label><span
                        className="mb-1 block text-xs font-bold">Credit account</span><NativeSelect
                        value={creditAccount} onChange={(event) => setCreditAccount(event.target.value)}
                        className="h-11 w-full rounded-xl border bg-background px-3 text-sm">{accounts.map((account) =>
                        <option key={account.id}
                                value={account.id}>{account.code} · {account.name}</option>)}</NativeSelect></label>
                        <button type="button" onClick={() => void addEntry()} disabled={submitting}
                                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-black text-primary-foreground disabled:opacity-50">{submitting ?
                            <Loader2 className="h-4 w-4 animate-spin"/> : <BookOpenCheck className="h-4 w-4"/>} Create
                            draft entry
                        </button>
                    </div>
                </article>

                <div className="space-y-6">
                    <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                        <div className="flex items-center gap-2 border-b p-5"><Scale className="h-5 w-5 text-primary"/>
                            <h2 className="text-lg font-black">Trial balance</h2></div>
                        <div className="overflow-x-auto">
                            <table className="w-full min-w-[650px] text-sm">
                                <thead className="bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                                <tr>
                                    <th className="px-5 py-3">Account</th>
                                    <th className="px-5 py-3 text-right">Debit</th>
                                    <th className="px-5 py-3 text-right">Credit</th>
                                    <th className="px-5 py-3 text-right">Balance</th>
                                </tr>
                                </thead>
                                <tbody className="divide-y">{trial?.lines.map((line) => <tr key={line.account_id}>
                                    <td className="px-5 py-3"><span
                                        className="font-black">{line.code}</span> · {line.name}</td>
                                    <td className="px-5 py-3 text-right">{formatMoney(line.debit)}</td>
                                    <td className="px-5 py-3 text-right">{formatMoney(line.credit)}</td>
                                    <td className="px-5 py-3 text-right font-black">{formatMoney(line.balance)}</td>
                                </tr>)}</tbody>
                            </table>
                        </div>
                    </article>
                    <article className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                        <div className="border-b p-5"><h2 className="text-lg font-black">Journal entries</h2></div>
                        <div className="divide-y">{entries.map((entry) => <div key={entry.id}
                                                                               className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
                            <div><p className="font-black">{entry.entry_number}</p><p
                                className="mt-1 text-sm">{entry.description}</p><p
                                className="mt-1 text-xs text-muted-foreground">{entry.entry_date} · {formatMoney(entry.total_debit)} · {entry.status}</p>
                            </div>
                            {entry.status === "draft" && <button type="button" onClick={async () => {
                                const posted = await postJournalEntry(entry.id, selectedCompanyId);
                                setEntries((current) => current.map((item) => item.id === posted.id ? posted : item));
                                toast.success("Journal entry posted");
                            }}
                                                                 className="h-10 rounded-xl border border-primary px-4 text-xs font-black text-primary">Post
                                entry</button>}</div>)}{!loading && entries.length === 0 &&
                            <p className="p-8 text-center text-sm text-muted-foreground">No journal entries
                                yet.</p>}</div>
                    </article>
                </div>
            </section>
        </main>
    );
}

function Metric({label, value}: { label: string; value: string }) {
    return <article className="rounded-2xl border bg-card p-5 shadow-sm"><p
        className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</p><p
        className="mt-2 text-2xl font-black">{value}</p></article>;
}
