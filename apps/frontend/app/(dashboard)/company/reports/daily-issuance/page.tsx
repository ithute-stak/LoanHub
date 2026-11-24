"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { useAppData } from "@/provider/appDataProvider";
import {
    downloadDailyIssuanceReport,
    getDailyIssuanceReport,
    type DailyIssuanceReport,
} from "@/api/reports";

function dateInput(date: Date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

const money = (value: string) =>
    new Intl.NumberFormat("en-LS", {
        style: "currency", currency: "LSL", minimumFractionDigits: 2,
    }).format(Number(value));

export default function DailyIssuancePage() {
    const { branches } = useAppData();
    const initial = useMemo(() => {
        const now = new Date();
        return { start: dateInput(now), end: dateInput(now) };
    }, []);
    const [start, setStart] = useState(initial.start);
    const [showAll, setShowAll] = useState(true);
    const [end, setEnd] = useState(initial.end);
    const [branchId, setBranchId] = useState("");
    const [report, setReport] = useState<DailyIssuanceReport | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [downloading, setDownloading] = useState<string | null>(null);
    const requestId = useRef(0);
    const filters = useMemo(() => ({
        period_start: start,
        period_end: end,
        ...(branchId ? { branch_id: branchId } : {}),
    }), [start, end, branchId]);

    const refresh = useCallback(async () => {
        const currentRequest = ++requestId.current;
        const rangeDays = start && end ? Math.round((Date.parse(end) - Date.parse(start)) / 86400000) : NaN;
        if (!start || !end || !Number.isFinite(rangeDays) || rangeDays < 0 || rangeDays > 92 || end === "9999-12-31") {
            setError("Select a valid date range of no more than 93 calendar days.");
            setReport(null);
            return;
        }
        setLoading(true);
        setError("");
        try {
            const result = await getDailyIssuanceReport(filters);
            if (currentRequest === requestId.current) setReport(result);
        } catch {
            if (currentRequest === requestId.current) {
                setError("Unable to load this report. Check your reporting permissions and try again.");
                setReport(null);
            }
        } finally {
            if (currentRequest === requestId.current) setLoading(false);
        }
    }, [filters, start, end]);

    useEffect(() => { void refresh(); }, [refresh]);

    async function download(format: "csv" | "pdf" | "xlsx") {
        setDownloading(format);
        setError("");
        try {
            await downloadDailyIssuanceReport(filters, format);
        } catch {
            setError(`Unable to download the ${format.toUpperCase()} report.`);
        } finally {
            setDownloading(null);
        }
    }

    return (
        <main className="space-y-6 p-4 md:p-6">
            <header>
                <h1 className="text-2xl font-bold">Daily Loan Issuance Register</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                    Individual loans, clients, cash paid out, and current contractual repayment expectations.
                </p>
            </header>
            <section className="flex flex-wrap items-end gap-3 rounded-2xl border bg-card p-4">
                <button type="button" className="rounded-lg border px-3 py-2 text-sm font-semibold hover:bg-muted"
                    onClick={() => { const today = dateInput(new Date()); setStart(today); setEnd(today); }}>Today</button>
                <button type="button" className="rounded-lg border px-3 py-2 text-sm font-semibold hover:bg-muted"
                    onClick={() => { const today = new Date(); setStart(dateInput(new Date(today.getFullYear(), today.getMonth(), 1))); setEnd(dateInput(today)); }}>This month</button>
                <label className="grid gap-1 text-sm">From
                    <input aria-label="From date" className="rounded-lg border bg-background p-2" type="date" value={start} onChange={e => setStart(e.target.value)} />
                </label>
                <label className="grid gap-1 text-sm">To
                    <input aria-label="To date" className="rounded-lg border bg-background p-2" type="date" value={end} onChange={e => setEnd(e.target.value)} />
                </label>
                <label className="grid gap-1 text-sm">Branch
                    <select aria-label="Branch" className="rounded-lg border bg-background p-2" value={branchId} onChange={e => setBranchId(e.target.value)}>
                        <option value="">All authorized branches</option>
                        {branches.map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
                    </select>
                </label>
                <button type="button" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50" onClick={() => void refresh()} disabled={loading}>
                    <RefreshCw size={16} /> {loading ? "Loading…" : "Refresh"}
                </button>
            </section>
            {error && <p role="alert" className="rounded-xl border border-destructive p-3 text-sm text-destructive">{error}</p>}
            {report && (
                <>
                    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                        {[
                            ["Loans issued", report.totals.loans_issued.toLocaleString("en-LS")],
                            ["Principal issued", money(report.totals.principal_issued)],
                            ["Cash to borrowers", money(report.cash_to_borrowers ?? "0")],
                            ["Expected contractual return", money(report.totals.expected_contractual_return)],
                            ["Above principal", money(report.totals.expected_return_above_principal)],
                        ].map(([label, value]) => (
                            <article key={label} className="rounded-2xl border bg-card p-5">
                                <p className="text-sm text-muted-foreground">{label}</p>
                                <p className="mt-2 text-xl font-bold">{value}</p>
                            </article>
                        ))}
                    </section>
                    <div className="flex flex-wrap gap-2">
                        {(["csv", "pdf", "xlsx"] as const).map(format => (
                            <button key={format} type="button" disabled={downloading !== null} onClick={() => void download(format)}
                                className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium disabled:opacity-50">
                                <Download size={16} /> {downloading === format ? "Preparing…" : `Download ${format.toUpperCase()}`}
                            </button>
                        ))}
                    </div>
                    <section className="overflow-x-auto rounded-2xl border bg-card">
                        <table className="w-full min-w-[700px] text-sm">
                            <thead className="bg-muted/50 text-left">
                                <tr>{["Date", "Loans", "Principal (M)", "Expected return (M)", "Above principal (M)"].map(h => <th key={h} className="p-3">{h}</th>)}</tr>
                            </thead>
                            <tbody>
                                {report.daily.map(row => (
                                    <tr key={row.date} className="border-t">
                                        <td className="p-3">{row.date}</td>
                                        <td className="p-3">{row.loans_issued}</td>
                                        <td className="p-3">{money(row.principal_issued)}</td>
                                        <td className="p-3">{money(row.expected_contractual_return)}</td>
                                        <td className="p-3">{money(row.expected_return_above_principal)}</td>
                                    </tr>
                                ))}
                                {report.daily.length === 0 && <tr><td colSpan={5} className="p-6 text-center text-muted-foreground">No loans issued during this period.</td></tr>}
                            </tbody>
                        </table>
                    </section>
                    <p className="text-xs leading-5 text-muted-foreground">
                        Basis: {report.basis}. Expected contractual returns are not guaranteed collections.
                        Principal issued may differ from cash disbursed, especially for top-up loans.
                        Dates use the database disbursement timestamp.
                    </p>
                </>
            )}
        </main>
    );
}
