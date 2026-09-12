"use client";


import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
    CalendarClock,
    Download,
    FileChartColumn,
    Loader2,
    Play,
    RefreshCcw,
    Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "@/utils/toast";

import { downloadManagedFile } from "@/api/files";
import {
    createReportSchedule,
    deleteReportSchedule,
    generateReport,
    getReportSummary,
    listReports,
    listReportSchedules,
} from "@/api/reports";
import { IthutePoweredBy } from "@/components/brand/ithute-brand";
import { formatMoney } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import type { GeneratedReport, ReportSchedule, ReportSummary } from "@/types/reporting";
import { getErrorMessage } from "@/utils/apiError";

function isoDate(date: Date): string {
    return date.toISOString().slice(0, 10);
}

function metricLabel(key: string): string {
    return key.replaceAll("_", " ").replace(/\b\w/g, (value) => value.toUpperCase());
}

function metricValue(key: string, value: unknown): string {
    if (typeof value === "number" && Number.isFinite(value)) {
        if (/(balance|value|paid|portfolio)/.test(key)) return formatMoney(value);
        if (key.includes("rate")) return `${value.toFixed(2)}%`;
        return value.toLocaleString();
    }
    return typeof value === "string" ? value : String(value ?? "—");
}

export function ReportCenter({
    mode,
    embedded = false,
}: {
    mode: "company" | "superadmin";
    embedded?: boolean;
}) {
    const { companies, branches, currentCompany } = useAppData();
    const [reports, setReports] = useState<GeneratedReport[]>([]);
    const [schedules, setSchedules] = useState<ReportSchedule[]>([]);
    const [summary, setSummary] = useState<ReportSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const today = new Date();
    const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
    const [periodStart, setPeriodStart] = useState(isoDate(monthStart));
    const [periodEnd, setPeriodEnd] = useState(isoDate(today));
    const [reportType, setReportType] = useState("executive");
    const [outputFormat, setOutputFormat] = useState("pdf");
    const [scopeType, setScopeType] = useState(mode === "superadmin" ? "platform" : "company");
    const [companyId, setCompanyId] = useState(mode === "company" ? currentCompany?.id ?? "" : "");
    const [branchId, setBranchId] = useState("");
    const [frequency, setFrequency] = useState("monthly");
    const [scheduleName, setScheduleName] = useState("Monthly management report");

    useEffect(() => {
        if (mode !== "company" || !currentCompany?.id) return;
        const timer = window.setTimeout(() => setCompanyId(currentCompany.id), 0);
        return () => window.clearTimeout(timer);
    }, [currentCompany?.id, mode]);

    const availableBranches = useMemo(
        () => branches.filter((branch) => !companyId || branch.company_id === companyId),
        [branches, companyId],
    );

    const parameters = useMemo(() => ({
        scope_type: scopeType,
        company_id: companyId || undefined,
        branch_id: branchId || undefined,
        period_start: periodStart,
        period_end: periodEnd,
    }), [branchId, companyId, periodEnd, periodStart, scopeType]);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [reportItems, scheduleItems, summaryData] = await Promise.all([
                listReports({ company_id: companyId || undefined, branch_id: branchId || undefined }),
                listReportSchedules({ company_id: companyId || undefined }),
                getReportSummary(parameters),
            ]);
            setReports(reportItems);
            setSchedules(scheduleItems);
            setSummary(summaryData);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not load report centre"));
        } finally {
            setLoading(false);
        }
    }, [branchId, companyId, parameters]);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    async function runReport() {
        setSubmitting(true);
        try {
            const report = await generateReport({
                report_type: reportType,
                output_format: outputFormat,
                scope_type: scopeType,
                company_id: companyId || undefined,
                branch_id: branchId || undefined,
                period_start: periodStart,
                period_end: periodEnd,
            });
            setReports((current) => [report, ...current]);
            toast.success("Report generated successfully");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Report could not be generated"));
        } finally {
            setSubmitting(false);
        }
    }

    async function addSchedule() {
        setSubmitting(true);
        try {
            const schedule = await createReportSchedule({
                name: scheduleName,
                report_type: reportType,
                frequency,
                output_format: outputFormat,
                scope_type: scopeType,
                company_id: companyId || undefined,
                branch_id: branchId || undefined,
                recipients: [],
                is_active: true,
            });
            setSchedules((current) => [schedule, ...current]);
            toast.success("Automatic report schedule created");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Schedule could not be created"));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <main className="space-y-6">
{!embedded && (
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div><div className="flex items-center gap-2 text-primary"><FileChartColumn className="h-5 w-5" /><span className="text-xs font-black uppercase tracking-[0.16em]">Business intelligence</span></div><h1 className="mt-2 text-3xl font-black">Automated report centre</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Generate daily, weekly, monthly and annual operational, portfolio, financial, performance and compliance reports.</p></div>
                    <div className="flex items-center gap-3"><IthutePoweredBy /><button type="button" onClick={() => void load()} className="rounded-xl border p-2.5" title="Refresh"><RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button></div>
                </div>
            </section>
            )}

            {summary && (
                <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    {Object.entries(summary.metrics).slice(0, 8).map(([key, value]) => (
                        <article key={key} className="rounded-2xl border bg-card p-5 shadow-sm"><p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{metricLabel(key)}</p><p className="mt-2 text-2xl font-black">{metricValue(key, value)}</p></article>
                    ))}
                </section>
            )}

            <section className="grid gap-6 xl:grid-cols-[390px_minmax(0,1fr)]">
                <aside className="space-y-6">
                    <article className="rounded-3xl border bg-card p-5 shadow-sm">
                        <h2 className="text-lg font-black">Generate report</h2>
                        <div className="mt-4 space-y-3">
                            {mode === "superadmin" && <NativeSelect value={scopeType} onChange={(event) => { setScopeType(event.target.value); if (event.target.value === "platform") { setCompanyId(""); setBranchId(""); } }} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold"><option value="platform">Whole platform</option><option value="company">Specific company</option><option value="branch">Specific branch</option></NativeSelect>}
                            {mode === "superadmin" && scopeType !== "platform" && <NativeSelect value={companyId} onChange={(event) => { setCompanyId(event.target.value); setBranchId(""); }} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold"><option value="">Select company</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}</NativeSelect>}
                            {(scopeType === "branch" || mode === "company") && <NativeSelect value={branchId} onChange={(event) => { setBranchId(event.target.value); if (event.target.value) setScopeType("branch"); else if (mode === "company") setScopeType("company"); }} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold"><option value="">All branches</option>{availableBranches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</NativeSelect>}
                            <NativeSelect value={reportType} onChange={(event) => setReportType(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold"><option value="executive">Executive summary</option><option value="operations">Operations</option><option value="financial">Financial</option><option value="portfolio">Loan portfolio</option><option value="performance">Performance</option><option value="compliance">Compliance</option></NativeSelect>
                            <NativeSelect value={outputFormat} onChange={(event) => setOutputFormat(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold"><option value="pdf">PDF document</option><option value="csv">CSV data file</option></NativeSelect>
                            <div className="grid grid-cols-2 gap-3"><label><span className="mb-1 block text-xs font-bold">From</span><Input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm" /></label><label><span className="mb-1 block text-xs font-bold">To</span><Input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm" /></label></div>
                            <button type="button" onClick={() => void runReport()} disabled={submitting || (scopeType !== "platform" && !companyId)} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-black text-primary-foreground disabled:opacity-50">{submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Generate now</button>
                        </div>
                    </article>

                    <article className="rounded-3xl border bg-card p-5 shadow-sm">
                        <div className="flex items-center gap-2"><CalendarClock className="h-5 w-5 text-primary" /><h2 className="text-lg font-black">Automatic schedule</h2></div>
                        <div className="mt-4 space-y-3"><Input value={scheduleName} onChange={(event) => setScheduleName(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm" /><NativeSelect value={frequency} onChange={(event) => setFrequency(event.target.value)} className="h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold"><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="annual">Annual</option></NativeSelect><button type="button" onClick={() => void addSchedule()} disabled={submitting || (scopeType !== "platform" && !companyId)} className="h-11 w-full rounded-xl border border-primary text-sm font-black text-primary disabled:opacity-50">Create schedule</button></div>
                    </article>
                </aside>

                <div className="space-y-6">
                    <article className="overflow-hidden rounded-3xl border bg-card shadow-sm"><div className="border-b p-5"><h2 className="text-lg font-black">Generated reports</h2><p className="mt-1 text-sm text-muted-foreground">Downloadable branded records stored in the file centre.</p></div><div className="divide-y">{reports.map((report) => <div key={report.id} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-black">{report.title}</p><p className="mt-1 text-xs text-muted-foreground">{report.reference} · {report.period_start} to {report.period_end} · {report.output_format.toUpperCase()}</p></div>{report.file && <button type="button" onClick={() => void downloadManagedFile(report.file!)} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-4 text-xs font-black hover:border-primary hover:text-primary"><Download className="h-4 w-4" /> Download</button>}</div>)}{!loading && reports.length === 0 && <p className="p-10 text-center text-sm text-muted-foreground">No reports have been generated yet.</p>}</div></article>
                    <article className="overflow-hidden rounded-3xl border bg-card shadow-sm"><div className="border-b p-5"><h2 className="text-lg font-black">Scheduled reports</h2></div><div className="divide-y">{schedules.map((schedule) => <div key={schedule.id} className="flex items-center justify-between gap-4 p-5"><div><p className="font-black">{schedule.name}</p><p className="mt-1 text-xs capitalize text-muted-foreground">{schedule.frequency} · {schedule.report_type} · next {new Date(schedule.next_run_at).toLocaleString("en-LS")}</p></div><button type="button" onClick={async () => { await deleteReportSchedule(schedule.id); setSchedules((current) => current.filter((item) => item.id !== schedule.id)); }} className="rounded-xl border p-2 text-red-600"><Trash2 className="h-4 w-4" /></button></div>)}{schedules.length === 0 && <p className="p-8 text-center text-sm text-muted-foreground">No automatic schedules configured.</p>}</div></article>
                </div>
            </section>
        </main>
    );
}
