"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import {
    AlertCircle,
    BadgeDollarSign,
    ContactRound,
    FileDown,
    FileSearch,
    Gauge,
    History,
    ListChecks,
    HandCoins,
    Loader2,
    Pencil,
    PlusCircle,
    Search,
    ShieldAlert,
    ShieldCheck,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { originationApi } from "@/api/origination";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";
import type { OriginationApplication } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";

type CdasEmployee = {
    EmployeeNo: string;
    Name: string | null;
    Surname: string | null;
    DOB: string | null;
    Department: string | null;
    JoiningDate: string | null;
    TerminationDate: string | null;
};

type ProviderRecord = Record<string, unknown>;
type LoadingAction = "employee" | "affordability" | "all" | "own" | "active" | null;

type EmployeeLookupResponse = {
    ok: boolean;
    employee: CdasEmployee;
    application_id?: string;
    borrower_id?: string;
    payroll_profile?: { id: string; employee_number: string; verified: boolean; verified_at: string | null; department: string | null };
};
type AffordabilityResponse = { ok: boolean; affordability: number };
type DeductionsResponse = { ok: boolean; deductions: ProviderRecord[] };
type ActiveDeductionResponse = { ok: boolean; deduction: ProviderRecord };
type ReadFeedbackKind = "employee" | "affordability" | "deductions" | "record";
type ReadFeedback = {
    kind: ReadFeedbackKind;
    title: string;
    description: string;
    records: Array<{ title: string; record: ProviderRecord }>;
};
type CdasRequestBudget = {
    environment: string;
    request_date: string;
    limit: number;
    used: number;
    remaining: number;
    last_request_at: string | null;
};

const EMPLOYEE_DETAILS: Array<{ key: keyof CdasEmployee; label: string }> = [
    { key: "EmployeeNo", label: "Employee number" },
    { key: "Name", label: "Name" },
    { key: "Surname", label: "Surname" },
    { key: "DOB", label: "Date of birth" },
    { key: "Department", label: "Department" },
    { key: "JoiningDate", label: "Joining date" },
    { key: "TerminationDate", label: "Termination date" },
];

const DEDUCTION_STATUSES = [
    [1, "Registered"],
    [2, "Reserved"],
    [3, "Reviewed"],
    [4, "Approved"],
    [5, "Active"],
    [6, "Cancelled"],
    [7, "Settled"],
    [8, "Auto-settled / Expired"],
    [9, "Deleted"],
    [10, "Changed"],
] as const;


const KNOWN_CDAS_AGENCIES: Record<string, string> = {
    "2409": "L.A.T. Subscription",
    "2576": "LESOTHO TEACHERS TRADE UNION",
    "2261": "Gap Funeral Services",
    "2330": "Thusong Financial Services",
    "2355": "PALT Membership Subscriptions",
};

function recordValue(record: ProviderRecord, ...keys: string[]): unknown {
    const entries = Object.entries(record);
    for (const key of keys) {
        const direct = record[key];
        if (direct !== undefined && direct !== null && direct !== "") return direct;
        const match = entries.find(([candidate]) => candidate.toLowerCase() === key.toLowerCase());
        if (match && match[1] !== undefined && match[1] !== null && match[1] !== "") return match[1];
    }
    return null;
}

function deductionItemCode(record: ProviderRecord): string {
    const value = recordValue(record, "ItemCode", "ItemCodeID", "AgencyCode", "DeductionCode", "DeductionType");
    return value === null ? "" : String(value);
}

function deductionAgencyName(record: ProviderRecord): string {
    const providerName = recordValue(
        record,
        "AgencyName",
        "DeductionName",
        "DeductionTypeName",
        "CompanyName",
        "Description",
        "PolicyName",
    );
    if (providerName) return String(providerName);
    const code = deductionItemCode(record);
    return KNOWN_CDAS_AGENCIES[code] || "—";
}

function deductionStatusLabel(record: ProviderRecord): string {
    const raw = recordValue(record, "Status", "DeductionStatusName");
    if (raw) return String(raw);
    const numeric = Number(recordValue(record, "DeductionStatus", "StatusCode"));
    const match = DEDUCTION_STATUSES.find(([value]) => value === numeric);
    return match?.[1] || (Number.isFinite(numeric) && numeric > 0 ? String(numeric) : "—");
}

function moneyValue(record: ProviderRecord): string {
    const raw = recordValue(record, "DeductionAmount", "Amount", "MonthlyDeduction");
    const amount = Number(raw ?? 0);
    if (!Number.isFinite(amount)) return displayValue(raw);
    return "M " + amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCdasPeriod(value: unknown): string {
    if (value === null || value === undefined || value === "") return "—";
    const raw = String(value).trim();
    const monthMatch = raw.match(/^(\d{4})[-/]?(\d{2})$/);
    if (monthMatch) {
        const date = new Date(Date.UTC(Number(monthMatch[1]), Number(monthMatch[2]) - 1, 1));
        return new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric", timeZone: "UTC" }).format(date);
    }
    const date = new Date(raw);
    if (!Number.isNaN(date.getTime())) {
        return new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "short", year: "numeric" }).format(date);
    }
    return raw;
}

function deductionEffectiveMonth(record: ProviderRecord): string {
    const value = recordValue(record, "EffectiveMonth", "EffectiveDate", "StartMonth");
    return formatCdasPeriod(value);
}

function deductionExpiry(record: ProviderRecord): string {
    const value = recordValue(record, "ExpiryMonth", "ExpiryDate", "EndMonth", "SettlementDate");
    return formatCdasPeriod(value);
}

function deductionStatusClasses(status: string): string {
    const normalized = status.toLowerCase();
    if (normalized.includes("active") || normalized.includes("approved")) {
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    }
    if (normalized.includes("settled")) {
        return "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300";
    }
    if (normalized.includes("cancel") || normalized.includes("deleted") || normalized.includes("expired")) {
        return "border-destructive/30 bg-destructive/10 text-destructive";
    }
    if (normalized.includes("review") || normalized.includes("reserved") || normalized.includes("registered")) {
        return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
    }
    return "border-border bg-muted/40 text-foreground";
}

function deductionReference(record: ProviderRecord): string {
    const value = recordValue(record, "ReferenceNo", "Reference", "PolicyLoanRefNo", "AuthorizationNo");
    return displayValue(value);
}

function DeductionResultsTable({ records }: { records: ProviderRecord[] }) {
    const [query, setQuery] = useState("");
    const [sortBy, setSortBy] = useState<"name" | "amount" | "status">("name");
    const normalizedQuery = query.trim().toLowerCase();

    const visibleRecords = records
        .filter((record) => {
            if (!normalizedQuery) return true;
            return [
                deductionItemCode(record),
                deductionAgencyName(record),
                deductionReference(record),
                deductionStatusLabel(record),
            ].some((value) => value.toLowerCase().includes(normalizedQuery));
        })
        .sort((left, right) => {
            if (sortBy === "amount") {
                const leftAmount = Number(recordValue(left, "DeductionAmount", "Amount", "MonthlyDeduction") ?? 0);
                const rightAmount = Number(recordValue(right, "DeductionAmount", "Amount", "MonthlyDeduction") ?? 0);
                return rightAmount - leftAmount;
            }
            if (sortBy === "status") {
                return deductionStatusLabel(left).localeCompare(deductionStatusLabel(right));
            }
            return deductionAgencyName(left).localeCompare(deductionAgencyName(right));
        });

    const visibleTotal = visibleRecords.reduce((sum, record) => {
        const amount = Number(recordValue(record, "DeductionAmount", "Amount", "MonthlyDeduction") ?? 0);
        return sum + (Number.isFinite(amount) ? amount : 0);
    }, 0);

    function exportCsv() {
        const csvEscape = (value: string) => `"${value.replaceAll('"', '""')}"`;
        const header = ["Item code", "Deduction / agency name", "Amount", "Effective month", "Expiry", "Reference no.", "Status"];
        const rows = visibleRecords.map((record) => [
            deductionItemCode(record),
            deductionAgencyName(record),
            moneyValue(record),
            deductionEffectiveMonth(record),
            deductionExpiry(record),
            deductionReference(record),
            deductionStatusLabel(record),
        ]);
        const csv = [header, ...rows].map((row) => row.map((value) => csvEscape(String(value))).join(",")).join("\n");
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `cdas-deductions-${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    }

    return (
        <div className="overflow-hidden rounded-2xl border bg-card">
            <div className="flex flex-col gap-3 border-b bg-muted/20 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="grid gap-2 sm:grid-cols-[minmax(260px,1fr)_180px] lg:min-w-[560px]">
                    <div className="relative">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            placeholder="Search code, deduction, reference or status"
                            className="pl-9 pr-16"
                        />
                        {query ? (
                            <button
                                type="button"
                                onClick={() => setQuery("")}
                                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs font-bold text-muted-foreground hover:bg-muted hover:text-foreground"
                            >
                                Clear
                            </button>
                        ) : null}
                    </div>
                    <select
                        value={sortBy}
                        onChange={(event) => setSortBy(event.target.value as "name" | "amount" | "status")}
                        className="h-10 rounded-md border bg-background px-3 text-sm"
                        aria-label="Sort deductions"
                    >
                        <option value="name">Sort by name</option>
                        <option value="amount">Sort by amount</option>
                        <option value="status">Sort by status</option>
                    </select>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <div className="rounded-xl border bg-background px-3 py-2 text-sm">
                        <span className="text-muted-foreground">Showing </span>
                        <strong>{visibleRecords.length}</strong>
                        <span className="text-muted-foreground"> of {records.length}</span>
                    </div>
                    <div className="rounded-xl border bg-background px-3 py-2 text-sm">
                        <span className="text-muted-foreground">Total </span>
                        <strong className="tabular-nums">
                            M {visibleTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </strong>
                    </div>
                    <Button type="button" variant="outline" onClick={exportCsv} disabled={!visibleRecords.length} className="print:hidden">
                        <FileDown className="h-4 w-4" />
                        Export CSV
                    </Button>
                    <Button type="button" variant="outline" onClick={() => window.print()} disabled={!visibleRecords.length} className="print:hidden">
                        <FileSearch className="h-4 w-4" />
                        Print / Save PDF
                    </Button>
                </div>
            </div>

            <div className="max-h-[62vh] overflow-auto">
                <table className="w-full min-w-[1050px] text-sm">
                    <thead className="sticky top-0 z-10 bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground shadow-sm">
                        <tr>
                            <th className="px-4 py-3">#</th>
                            <th className="sticky left-0 z-20 bg-muted px-4 py-3">Item code</th>
                            <th className="sticky left-[112px] z-20 bg-muted px-4 py-3">Deduction / agency name</th>
                            <th className="px-4 py-3 text-right">Amount</th>
                            <th className="px-4 py-3">Effective month</th>
                            <th className="px-4 py-3">Expiry</th>
                            <th className="px-4 py-3">Reference no.</th>
                            <th className="px-4 py-3">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {visibleRecords.length ? visibleRecords.map((record, index) => (
                            <tr key={index} className="group border-t align-top hover:bg-muted/30">
                                <td className="px-4 py-3 font-semibold text-muted-foreground">{index + 1}</td>
                                <td className="sticky left-0 z-10 bg-card px-4 py-3 font-mono font-black group-hover:bg-muted">{deductionItemCode(record) || "—"}</td>
                                <td className="sticky left-[112px] z-10 bg-card px-4 py-3 font-bold group-hover:bg-muted">{deductionAgencyName(record)}</td>
                                <td className="px-4 py-3 text-right font-black tabular-nums">{moneyValue(record)}</td>
                                <td className="px-4 py-3 font-semibold">{deductionEffectiveMonth(record)}</td>
                                <td className="px-4 py-3">{deductionExpiry(record)}</td>
                                <td className="px-4 py-3 font-mono text-xs font-bold">{deductionReference(record)}</td>
                                <td className="px-4 py-3">
                                    <Badge variant="outline" className={deductionStatusClasses(deductionStatusLabel(record))}>
                                        {deductionStatusLabel(record)}
                                    </Badge>
                                </td>
                            </tr>
                        )) : (
                            <tr>
                                <td colSpan={8} className="px-4 py-10 text-center text-sm text-muted-foreground">
                                    No deductions match the current search.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function displayValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
}

function EmployeeResultsTable({ record }: { record: ProviderRecord }) {
    const columns = [
        ["EmployeeNo", "Employee number"],
        ["Name", "Name"],
        ["Surname", "Surname"],
        ["DOB", "Date of birth"],
        ["Department", "Department"],
        ["JoiningDate", "Joining date"],
        ["TerminationDate", "Termination date"],
    ] as const;

    return (
        <div className="overflow-hidden rounded-2xl border bg-card">
            <div className="overflow-x-auto">
                <table className="w-full min-w-[1180px] text-sm">
                    <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
                            {columns.map(([key, label]) => (
                                <th
                                    key={key}
                                    className={key === "Department" ? "min-w-[300px] px-4 py-3" : "min-w-[140px] px-4 py-3"}
                                >
                                    {label}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        <tr className="border-t align-top">
                            {columns.map(([key]) => (
                                <td key={key} className="px-4 py-4 font-semibold">
                                    {displayValue(record[key])}
                                </td>
                            ))}
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function ProviderRecordCard({ record, title }: { record: ProviderRecord; title: string }) {
    return (
        <div className="overflow-hidden rounded-2xl border">
            <div className="border-b bg-muted/30 px-4 py-3 text-sm font-black">{title}</div>
            <dl className="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-3">
                {Object.entries(record).map(([key, value]) => (
                    <div key={key} className="min-w-0 bg-card p-4">
                        <dt className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{key}</dt>
                        <dd className="mt-1 break-words text-sm font-bold">{displayValue(value)}</dd>
                    </div>
                ))}
            </dl>
        </div>
    );
}

export default function CdasWorkspacePage() {
    const { activeRole } = useTenant();
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const [employeeNo, setEmployeeNo] = useState("");
    const [applications, setApplications] = useState<OriginationApplication[]>([]);
    const [selectedApplicationId, setSelectedApplicationId] = useState("");
    const [applicationsLoading, setApplicationsLoading] = useState(false);
    const [linkedPayrollProfile, setLinkedPayrollProfile] = useState<EmployeeLookupResponse["payroll_profile"] | null>(null);
    const [deductionStatus, setDeductionStatus] = useState(5);
    const [employee, setEmployee] = useState<CdasEmployee | null>(null);
    const [affordability, setAffordability] = useState<number | null>(null);
    const [allDeductions, setAllDeductions] = useState<ProviderRecord[] | null>(null);
    const [ownDeductions, setOwnDeductions] = useState<ProviderRecord[] | null>(null);
    const [activeDeduction, setActiveDeduction] = useState<ProviderRecord | null>(null);
    const [requestBudget, setRequestBudget] = useState<CdasRequestBudget | null>(null);
    const [budgetLoading, setBudgetLoading] = useState(false);
    const [loadingAction, setLoadingAction] = useState<LoadingAction>(null);
    const [error, setError] = useState<string | null>(null);
    const [readFeedback, setReadFeedback] = useState<ReadFeedback | null>(null);

    const normalizedEmployeeNo = employeeNo.trim();
    const busy = loadingAction !== null;

    function resetResults() {
        setEmployee(null);
        setLinkedPayrollProfile(null);
        setAffordability(null);
        setAllDeductions(null);
        setOwnDeductions(null);
        setActiveDeduction(null);
        setError(null);
    }

    async function loadApplications() {
        if (applicationsLoading) return;
        setApplicationsLoading(true);
        setError(null);
        try {
            const rows = await originationApi.listApplications();
            const eligible = rows.filter((application) =>
                ["draft", "submitted", "under_review", "approved"].includes(application.status),
            );
            const requestedApplicationId = typeof window !== "undefined"
                ? new URLSearchParams(window.location.search).get("application")
                : null;
            setApplications(eligible);
            setSelectedApplicationId((current: string) => {
                if (current) return current;
                if (requestedApplicationId && eligible.some((application) => application.id === requestedApplicationId)) {
                    return requestedApplicationId;
                }
                return eligible[0]?.id || "";
            });
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "Loan applications could not be loaded."));
        } finally {
            setApplicationsLoading(false);
        }
    }

    async function refreshRequestBudget() {
        if (budgetLoading) return;
        setBudgetLoading(true);
        try {
            const response = await api.get<CdasRequestBudget>("/cdas/request-budget");
            setRequestBudget(response.data);
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS request allowance could not be loaded."));
        } finally {
            setBudgetLoading(false);
        }
    }

    async function verifyEmployee(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!normalizedEmployeeNo || busy) return;
        setLoadingAction("employee");
        setError(null);
        try {
            const endpoint = selectedApplicationId
                ? `/cdas/applications/${selectedApplicationId}/verify-employee`
                : "/cdas/employees/verify";
            const response = await api.post<EmployeeLookupResponse>(endpoint, {
                employee_no: normalizedEmployeeNo,
            });
            setEmployee(response.data.employee);
            setLinkedPayrollProfile(response.data.payroll_profile ?? null);
            setReadFeedback({
                kind: "employee",
                title: "Employee verified",
                description: "CDAS returned the employee record successfully.",
                records: [{ title: "Employee details", record: { ...response.data.employee } }],
            });
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS employee verification failed."));
        } finally {
            setLoadingAction(null);
        }
    }

    async function checkAffordability() {
        if (!normalizedEmployeeNo || busy) return;
        setLoadingAction("affordability");
        setError(null);
        try {
            const response = await api.post<AffordabilityResponse>("/cdas/employees/affordability", {
                employee_no: normalizedEmployeeNo,
            });
            setAffordability(response.data.affordability);
            setReadFeedback({
                kind: "affordability",
                title: "Affordability result",
                description: "CDAS returned the employee affordability amount.",
                records: [{
                    title: "CDAS affordability",
                    record: {
                        EmployeeNo: normalizedEmployeeNo,
                        Affordability: "M " + response.data.affordability.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                        }),
                    },
                }],
            });
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS affordability check failed."));
        } finally {
            setLoadingAction(null);
        }
    }

    async function viewAllDeductions() {
        if (!normalizedEmployeeNo || busy) return;
        setLoadingAction("all");
        setError(null);
        try {
            const response = await api.post<DeductionsResponse>("/cdas/deductions/all", {
                employee_no: normalizedEmployeeNo,
            });
            setAllDeductions(response.data.deductions);
            setReadFeedback({
                kind: "deductions",
                title: "All third-party deductions",
                description: response.data.deductions.length
                    ? `CDAS returned ${response.data.deductions.length} deduction record${response.data.deductions.length === 1 ? "" : "s"}.`
                    : "CDAS returned no third-party deductions for this employee.",
                records: response.data.deductions.map((record, index) => ({
                    title: `Deduction ${index + 1}`,
                    record,
                })),
            });
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS third-party deduction lookup failed."));
        } finally {
            setLoadingAction(null);
        }
    }

    async function viewOwnDeductions() {
        if (!normalizedEmployeeNo || busy) return;
        setLoadingAction("own");
        setError(null);
        try {
            const response = await api.post<DeductionsResponse>("/cdas/deductions/own", {
                employee_no: normalizedEmployeeNo,
                deduction_status: deductionStatus,
            });
            setOwnDeductions(response.data.deductions);
            setReadFeedback({
                kind: "deductions",
                title: "Own deductions by status",
                description: response.data.deductions.length
                    ? `CDAS returned ${response.data.deductions.length} matching deduction record${response.data.deductions.length === 1 ? "" : "s"}.`
                    : "CDAS returned no deductions for the selected status.",
                records: response.data.deductions.map((record, index) => ({
                    title: `Own deduction ${index + 1}`,
                    record,
                })),
            });
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS own-deduction lookup failed."));
        } finally {
            setLoadingAction(null);
        }
    }

    function openDeductionResults(title: string, emptyDescription: string, records: ProviderRecord[]) {
        setReadFeedback({
            kind: "deductions",
            title,
            description: records.length
                ? `CDAS returned ${records.length} deduction record${records.length === 1 ? "" : "s"}.`
                : emptyDescription,
            records: records.map((record, index) => ({
                title: `Deduction ${index + 1}`,
                record,
            })),
        });
    }

    async function viewActiveApprovedDeduction() {
        if (!normalizedEmployeeNo || busy) return;
        setLoadingAction("active");
        setError(null);
        try {
            const response = await api.post<ActiveDeductionResponse>("/cdas/deductions/active-approved", {
                employee_no: normalizedEmployeeNo,
            });
            setActiveDeduction(response.data.deduction);
            setReadFeedback({
                kind: "deductions",
                title: "Active / approved deduction",
                description: "CDAS returned the current active or approved deduction.",
                records: [{ title: "Active / approved deduction", record: response.data.deduction }],
            });
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS active/approved deduction lookup failed."));
        } finally {
            setLoadingAction(null);
        }
    }

    return (
        <div className="loanhub-page space-y-5 2xl:space-y-6">
            <section className="rounded-2xl border bg-card p-5 shadow-sm 2xl:rounded-3xl 2xl:p-7">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="max-w-4xl">
                        <div className="mb-3 flex flex-wrap gap-2"><Badge variant="secondary">LoanHub-managed CDAS operations</Badge><Badge variant="outline">CDAS API v1.5</Badge></div>
                        <h1 className="flex items-center gap-2 text-2xl font-black tracking-tight sm:text-3xl">
                            <ShieldCheck className="h-7 w-7 text-primary" />
                            CDAS lending workspace
                        </h1>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            Verify employees and affordability against CDAS, then manage payroll deductions from approved LoanHub loans.
                            CDAS Autopilot can safely re-optimise eligible deductions after confirmed payments and during the monthly affordability window. State-changing manual actions remain separated behind explicit confirmation and audit logging.
                        </p>
                    </div>
                    <div className="flex min-w-56 flex-col items-start gap-2 lg:items-end">
                        <Badge>Manual requests only</Badge><Badge variant="outline">Autopilot enabled</Badge>
                        {requestBudget ? (
                            <div className="rounded-xl border bg-muted/30 px-3 py-2 text-xs lg:text-right">
                                <p className="font-black tabular-nums">{requestBudget.remaining} / {requestBudget.limit} requests remaining</p>
                                <p className="mt-1 text-muted-foreground">{requestBudget.environment.toUpperCase()} · {requestBudget.request_date}</p>
                            </div>
                        ) : null}
                        <Button type="button" size="sm" variant="outline" disabled={budgetLoading} onClick={() => void refreshRequestBudget()}>
                            {budgetLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gauge className="h-4 w-4" />}
                            {requestBudget ? "Refresh allowance" : "Check request allowance"}
                        </Button>
                    </div>
                </div>
            </section>

            {canManage && (
                <div className="grid gap-4 md:grid-cols-2">
                    <Card className="border-destructive/20">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base"><ShieldAlert className="h-5 w-5 text-destructive" /> Deduction management</CardTitle>
                            <CardDescription>Add approved loans to CDAS, track status, reconcile exceptions and manage active deductions from one LoanHub-first workflow.</CardDescription>
                        </CardHeader>
                        <CardContent className="flex flex-wrap gap-2"><Button asChild><Link href="/company/cdas/manage">Manage deductions</Link></Button><Button asChild variant="outline"><Link href="/company/cdas/operations">Advanced deduction operations</Link></Button></CardContent>
                    </Card>
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base"><FileDown className="h-5 w-5" /> Statements & transactions</CardTitle>
                            <CardDescription>Manually retrieve the documented CDAS output file or statement for a selected month.</CardDescription>
                        </CardHeader>
                        <CardContent><Button asChild variant="outline"><Link href="/company/cdas/documents">Open document retrieval</Link></Button></CardContent>
                    </Card>
                </div>
            )}

            {canManage && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <ShieldCheck className="h-5 w-5 text-primary" /> Deduction lifecycle
                        </CardTitle>
                        <CardDescription>
                            The core CDAS deduction actions are available directly from LoanHub. State-changing actions remain protected by explicit confirmation and audit logging.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        <Button asChild className="h-auto justify-start py-4">
                            <Link href="/company/cdas/operations?action=register#lifecycle">
                                <PlusCircle className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Add deduction</strong><span className="block text-xs font-normal opacity-80">Register an approved LoanHub loan with CDAS</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/operations?action=review#lifecycle">
                                <FileSearch className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Review deduction</strong><span className="block text-xs font-normal text-muted-foreground">Send the documented Review lifecycle action</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/operations?action=approve#lifecycle">
                                <ShieldCheck className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Approve deduction</strong><span className="block text-xs font-normal text-muted-foreground">Approve a reviewed deduction</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/operations?action=modify#modify-active">
                                <Pencil className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Modify active deduction</strong><span className="block text-xs font-normal text-muted-foreground">Change allowed active-deduction values</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/operations?action=cancel#lifecycle">
                                <ShieldAlert className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Cancel / reject deduction</strong><span className="block text-xs font-normal text-muted-foreground">Use documented request code 6</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/operations?action=settle#settle">
                                <HandCoins className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Settle deduction</strong><span className="block text-xs font-normal text-muted-foreground">Submit a documented settlement reason</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/manage">
                                <ShieldAlert className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Reconcile / manage</strong><span className="block text-xs font-normal text-muted-foreground">Resolve uncertain provider state and manage linked loans</span></span>
                            </Link>
                        </Button>
                    </CardContent>
                </Card>
            )}

            {canManage && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><History className="h-5 w-5" /> CDAS history & control records</CardTitle>
                        <CardDescription>
                            LoanHub mirrors the original portal&apos;s reporting and audit functions from its durable CDAS provider ledger and immutable activity log.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/history?tab=transactions">
                                <ListChecks className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Transaction log</strong><span className="block text-xs font-normal text-muted-foreground">Provider calls, status and reconciliation state</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/history?tab=deductions">
                                <History className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Deduction history</strong><span className="block text-xs font-normal text-muted-foreground">Append-only lifecycle events by deduction</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/activity">
                                <ShieldCheck className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Audit log</strong><span className="block text-xs font-normal text-muted-foreground">Actor, request ID, before/after and timestamps</span></span>
                            </Link>
                        </Button>
                        <Button asChild variant="outline" className="h-auto justify-start py-4">
                            <Link href="/company/cdas/documents">
                                <FileDown className="h-5 w-5" />
                                <span className="text-left"><strong className="block">Download reports</strong><span className="block text-xs font-normal text-muted-foreground">Output File and Statement from CDAS</span></span>
                            </Link>
                        </Button>
                    </CardContent>
                </Card>
            )}

            {canManage && (
                <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Original CDAS portal-only functions</AlertTitle>
                    <AlertDescription>
                        The original portal also shows Consolidation, Bulk Upload, Manage User, Session Log and Inbox screens.
                        CDAS API v1.5 does not document third-party endpoints for those screens, so LoanHub does not fabricate provider calls for them.
                        Consolidation is preserved as settlement reason 3 where the official API documents it; user administration, security sessions and inbox functions remain governed by LoanHub&apos;s own administration, security and notification systems.
                    </AlertDescription>
                </Alert>
            )}

            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <ContactRound className="h-5 w-5" /> Employee verification
                    </CardTitle>
                    <CardDescription>
                        Verify an employee directly, or select a LoanHub application first to link the verified CDAS payroll profile to that borrower.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form className="space-y-4" onSubmit={verifyEmployee}>
                        <div className="grid gap-3 lg:grid-cols-[1fr_auto]">
                            <div className="space-y-2">
                                <Label htmlFor="cdas-application">Loan application (optional)</Label>
                                <select
                                    id="cdas-application"
                                    value={selectedApplicationId}
                                    disabled={busy || applicationsLoading}
                                    onChange={(event) => {
                                        setSelectedApplicationId(event.target.value);
                                        resetResults();
                                    }}
                                    className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                                >
                                    <option value="">Verify employee only · do not link</option>
                                    {applications.map((application) => (
                                        <option key={application.id} value={application.id}>
                                            {application.application_reference} · {application.borrower_name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex items-end">
                                <Button type="button" variant="outline" disabled={applicationsLoading || busy} onClick={() => void loadApplications()}>
                                    {applicationsLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSearch className="h-4 w-4" />}
                                    Load applications
                                </Button>
                            </div>
                        </div>
                        <div className="flex flex-col gap-2 sm:flex-row">
                            <Input
                                id="cdas-employee-number"
                                value={employeeNo}
                                disabled={busy}
                                onChange={(event) => {
                                    setEmployeeNo(event.target.value);
                                    resetResults();
                                }}
                                placeholder="Enter CDAS employee number"
                                autoComplete="off"
                            />
                            <Button type="submit" disabled={busy || !normalizedEmployeeNo} className="sm:min-w-44">
                                {loadingAction === "employee" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                                Verify Employee
                            </Button>
                        </div>
                    </form>
                    {linkedPayrollProfile ? (
                        <div className="mt-4 rounded-2xl border bg-muted/20 p-4 text-sm">
                            <p className="font-black">Payroll profile linked to this application</p>
                            <p className="mt-1 text-muted-foreground">
                                Employee {linkedPayrollProfile.employee_number} · {linkedPayrollProfile.department || "Department not supplied"} · verified
                            </p>
                        </div>
                    ) : null}
                </CardContent>
            </Card>

            {error && (
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>CDAS request unsuccessful</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            <div className="grid gap-5 xl:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <BadgeDollarSign className="h-5 w-5" /> Affordability
                        </CardTitle>
                        <CardDescription>Request the affordability amount for this employee.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Button type="button" onClick={() => void checkAffordability()} disabled={busy || !normalizedEmployeeNo}>
                            {loadingAction === "affordability" ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeDollarSign className="h-4 w-4" />}
                            Check Affordability
                        </Button>
                        {affordability !== null && (
                            <div className="rounded-2xl border bg-muted/20 p-5">
                                <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">CDAS affordability</p>
                                <p className="mt-2 text-3xl font-black tabular-nums">M {affordability.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <HandCoins className="h-5 w-5" /> All third-party deductions
                        </CardTitle>
                        <CardDescription>View the employee&apos;s deductions across third parties.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Button type="button" variant="outline" onClick={() => void viewAllDeductions()} disabled={busy || !normalizedEmployeeNo}>
                            {loadingAction === "all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSearch className="h-4 w-4" />}
                            View All Deductions
                        </Button>
                        {allDeductions !== null && (
                            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-muted/20 p-4">
                                <div>
                                    <p className="text-sm font-black">
                                        {allDeductions.length
                                            ? `${allDeductions.length} deduction record${allDeductions.length === 1 ? "" : "s"} loaded`
                                            : "No third-party deductions found"}
                                    </p>
                                    <p className="mt-1 text-xs text-muted-foreground">
                                        Results are kept compact here; open the full 90% table to search, sort, total and export.
                                    </p>
                                </div>
                                {allDeductions.length > 0 && (
                                    <Button
                                        type="button"
                                        variant="secondary"
                                        onClick={() => openDeductionResults(
                                            "All third-party deductions",
                                            "CDAS returned no third-party deductions for this employee.",
                                            allDeductions,
                                        )}
                                    >
                                        <FileSearch className="h-4 w-4" />
                                        View results
                                    </Button>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            <div className="grid gap-5 xl:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <FileSearch className="h-5 w-5" /> Own deductions by status
                        </CardTitle>
                        <CardDescription>
                            View deductions belonging to the authenticated third party for a documented CDAS status code.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="cdas-deduction-status">Deduction status</Label>
                            <select
                                id="cdas-deduction-status"
                                value={deductionStatus}
                                disabled={busy}
                                onChange={(event) => setDeductionStatus(Number(event.target.value))}
                                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                            >
                                {DEDUCTION_STATUSES.map(([value, label]) => (
                                    <option key={value} value={value}>{value} — {label}</option>
                                ))}
                            </select>
                        </div>
                        <Button type="button" variant="outline" onClick={() => void viewOwnDeductions()} disabled={busy || !normalizedEmployeeNo}>
                            {loadingAction === "own" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSearch className="h-4 w-4" />}
                            View Own Deductions
                        </Button>
                        {ownDeductions !== null && (
                            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-muted/20 p-4">
                                <div>
                                    <p className="text-sm font-black">
                                        {ownDeductions.length
                                            ? `${ownDeductions.length} matching deduction record${ownDeductions.length === 1 ? "" : "s"} loaded`
                                            : "No deductions found for this status"}
                                    </p>
                                    <p className="mt-1 text-xs text-muted-foreground">
                                        Status {deductionStatus} — {DEDUCTION_STATUSES.find(([value]) => value === deductionStatus)?.[1] || "Unknown"}
                                    </p>
                                </div>
                                {ownDeductions.length > 0 && (
                                    <Button
                                        type="button"
                                        variant="secondary"
                                        onClick={() => openDeductionResults(
                                            "Own deductions by status",
                                            "CDAS returned no deductions for the selected status.",
                                            ownDeductions,
                                        )}
                                    >
                                        <FileSearch className="h-4 w-4" />
                                        View results
                                    </Button>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <ShieldCheck className="h-5 w-5" /> Active / approved deduction
                        </CardTitle>
                        <CardDescription>Fetch the employee&apos;s active or approved deduction record documented by CDAS.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Button type="button" variant="outline" onClick={() => void viewActiveApprovedDeduction()} disabled={busy || !normalizedEmployeeNo}>
                            {loadingAction === "active" ? <Loader2 className="h-4 w-4 animate-spin" /> : <HandCoins className="h-4 w-4" />}
                            View Active / Approved
                        </Button>
                        {activeDeduction && (
                            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-muted/20 p-4">
                                <div>
                                    <p className="text-sm font-black">{deductionAgencyName(activeDeduction)}</p>
                                    <p className="mt-1 text-xs text-muted-foreground">
                                        {deductionItemCode(activeDeduction) || "No item code"} · {moneyValue(activeDeduction)} · {deductionStatusLabel(activeDeduction)}
                                    </p>
                                </div>
                                <Button
                                    type="button"
                                    variant="secondary"
                                    onClick={() => openDeductionResults(
                                        "Active / approved deduction",
                                        "CDAS returned no active or approved deduction.",
                                        [activeDeduction],
                                    )}
                                >
                                    <FileSearch className="h-4 w-4" />
                                    View result
                                </Button>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {employee && (
                <Card>
                    <CardHeader>
                        <CardTitle>Verified employee</CardTitle>
                        <CardDescription>Only the seven Employee Details fields documented by CDAS are shown here.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-hidden rounded-2xl border">
                            <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/30 p-4">
                                <div>
                                    <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">CDAS employee</p>
                                    <p className="mt-1 text-lg font-black">
                                        {[employee.Name, employee.Surname].filter(Boolean).join(" ") || employee.EmployeeNo}
                                    </p>
                                </div>
                                <Badge>Verified response</Badge>
                            </div>
                            <dl className="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-3">
                                {EMPLOYEE_DETAILS.map(({ key, label }) => (
                                    <div key={key} className="bg-card p-4">
                                        <dt className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</dt>
                                        <dd className="mt-1 break-words text-sm font-bold">{employee[key] || "—"}</dd>
                                    </div>
                                ))}
                            </dl>
                        </div>
                    </CardContent>
                </Card>
            )}

            <Dialog open={readFeedback !== null} onOpenChange={(open) => { if (!open) setReadFeedback(null); }}>
                <DialogContent className="w-[90vw] max-w-[90vw] max-h-[90vh] overflow-hidden print:static print:max-h-none print:w-full print:max-w-none print:border-0 print:shadow-none">
                    <DialogHeader className="print:mb-4">
                        <DialogTitle>{readFeedback?.title || "CDAS result"}</DialogTitle>
                        <DialogDescription>
                            {readFeedback?.kind === "deductions" ? (
                                <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                                    <span className="font-semibold text-foreground">
                                        Employee {employee?.EmployeeNo || normalizedEmployeeNo || "—"}
                                    </span>
                                    {employee && (employee.Name || employee.Surname) ? (
                                        <>
                                            <span aria-hidden="true">·</span>
                                            <span>{[employee.Name, employee.Surname].filter(Boolean).join(" ")}</span>
                                        </>
                                    ) : null}
                                    <span aria-hidden="true">·</span>
                                    <span>
                                        {readFeedback.records.length} deduction record{readFeedback.records.length === 1 ? "" : "s"}
                                    </span>
                                </span>
                            ) : (
                                readFeedback?.description
                            )}
                        </DialogDescription>
                    </DialogHeader>

                    {readFeedback?.kind === "deductions" ? (
                        readFeedback.records.length ? (
                            <DeductionResultsTable records={readFeedback.records.map((item) => item.record)} />
                        ) : (
                            <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                                No matching CDAS deductions were returned.
                            </div>
                        )
                    ) : readFeedback?.kind === "employee" ? (
                        readFeedback.records.length ? (
                            <EmployeeResultsTable record={readFeedback.records[0].record} />
                        ) : (
                            <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                                No employee record was returned.
                            </div>
                        )
                    ) : (
                        <div className="max-h-[62vh] space-y-3 overflow-y-auto pr-1">
                            {readFeedback?.records.length ? (
                                readFeedback.records.map((item, index) => (
                                    <ProviderRecordCard key={item.title + index} title={item.title} record={item.record} />
                                ))
                            ) : (
                                <div className="rounded-2xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                                    No matching CDAS records were returned.
                                </div>
                            )}
                        </div>
                    )}

                    <DialogFooter showCloseButton className="print:hidden" />
                </DialogContent>
            </Dialog>

            <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Controlled CDAS usage</AlertTitle>
                <AlertDescription>
                    The provider documentation specifies a maximum of 400 requests per day per API user. LoanHub reserves a local allowance slot before every outbound CDAS HTTP request, including login and session refresh, and blocks locally at the limit. The allowance button above reads LoanHub only and does not contact CDAS.
                </AlertDescription>
            </Alert>
        </div>
    );
}
