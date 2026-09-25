"use client";

import { useState, type FormEvent } from "react";
import {
    AlertCircle,
    BadgeDollarSign,
    ContactRound,
    FileSearch,
    HandCoins,
    Loader2,
    Search,
    ShieldCheck,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
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

type EmployeeLookupResponse = { ok: boolean; employee: CdasEmployee };
type AffordabilityResponse = { ok: boolean; affordability: number };
type DeductionsResponse = { ok: boolean; deductions: ProviderRecord[] };
type ActiveDeductionResponse = { ok: boolean; deduction: ProviderRecord };

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

function displayValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
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
    const [employeeNo, setEmployeeNo] = useState("");
    const [deductionStatus, setDeductionStatus] = useState(5);
    const [employee, setEmployee] = useState<CdasEmployee | null>(null);
    const [affordability, setAffordability] = useState<number | null>(null);
    const [allDeductions, setAllDeductions] = useState<ProviderRecord[] | null>(null);
    const [ownDeductions, setOwnDeductions] = useState<ProviderRecord[] | null>(null);
    const [activeDeduction, setActiveDeduction] = useState<ProviderRecord | null>(null);
    const [loadingAction, setLoadingAction] = useState<LoadingAction>(null);
    const [error, setError] = useState<string | null>(null);

    const normalizedEmployeeNo = employeeNo.trim();
    const busy = loadingAction !== null;

    function resetResults() {
        setEmployee(null);
        setAffordability(null);
        setAllDeductions(null);
        setOwnDeductions(null);
        setActiveDeduction(null);
        setError(null);
    }

    async function verifyEmployee(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!normalizedEmployeeNo || busy) return;
        setLoadingAction("employee");
        setError(null);
        try {
            const response = await api.post<EmployeeLookupResponse>("/cdas/employees/verify", {
                employee_no: normalizedEmployeeNo,
            });
            setEmployee(response.data.employee);
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
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS own-deduction lookup failed."));
        } finally {
            setLoadingAction(null);
        }
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
                        <Badge variant="secondary" className="mb-3">CDAS reintegration · Read-only phases 2–4</Badge>
                        <h1 className="flex items-center gap-2 text-2xl font-black tracking-tight sm:text-3xl">
                            <ShieldCheck className="h-7 w-7 text-primary" />
                            CDAS lending workspace
                        </h1>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            Perform deliberate employee, affordability and deduction lookups against CDAS.
                            Nothing on this page runs in the background, and no deduction is created, reviewed,
                            approved, changed, cancelled or settled by these read-only actions.
                        </p>
                    </div>
                    <Badge>Manual requests only</Badge>
                </div>
            </section>

            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <ContactRound className="h-5 w-5" /> Employee number
                    </CardTitle>
                    <CardDescription>
                        Enter the employee number exactly as CDAS knows it. Each button below sends only the request you choose.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form className="space-y-4" onSubmit={verifyEmployee}>
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
                        <CardDescription>Phase 3 · Request the affordability amount for this employee.</CardDescription>
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
                        <CardDescription>Phase 4 · View the employee's deductions across third parties.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Button type="button" variant="outline" onClick={() => void viewAllDeductions()} disabled={busy || !normalizedEmployeeNo}>
                            {loadingAction === "all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSearch className="h-4 w-4" />}
                            View All Deductions
                        </Button>
                        {allDeductions !== null && (
                            <div className="space-y-3">
                                {allDeductions.length === 0 ? (
                                    <p className="rounded-xl border p-4 text-sm text-muted-foreground">CDAS returned no third-party deductions.</p>
                                ) : allDeductions.map((record, index) => (
                                    <ProviderRecordCard key={`all-${index}`} record={record} title={`Deduction ${index + 1}`} />
                                ))}
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
                            Phase 4 · View deductions belonging to the authenticated third party for a documented CDAS status code.
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
                            <div className="space-y-3">
                                {ownDeductions.length === 0 ? (
                                    <p className="rounded-xl border p-4 text-sm text-muted-foreground">CDAS returned no deductions for this status.</p>
                                ) : ownDeductions.map((record, index) => (
                                    <ProviderRecordCard key={`own-${index}`} record={record} title={`Own deduction ${index + 1}`} />
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <ShieldCheck className="h-5 w-5" /> Active / approved deduction
                        </CardTitle>
                        <CardDescription>Phase 4 · Fetch the active or approved deduction record documented by CDAS.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Button type="button" variant="outline" onClick={() => void viewActiveApprovedDeduction()} disabled={busy || !normalizedEmployeeNo}>
                            {loadingAction === "active" ? <Loader2 className="h-4 w-4 animate-spin" /> : <HandCoins className="h-4 w-4" />}
                            View Active / Approved
                        </Button>
                        {activeDeduction && <ProviderRecordCard record={activeDeduction} title="Active / approved deduction" />}
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

            <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Controlled CDAS usage</AlertTitle>
                <AlertDescription>
                    The provider documentation specifies a maximum of 400 requests per day per API user. LoanHub does not poll CDAS or run these reads automatically. Each lookup is initiated by a user action on this page.
                </AlertDescription>
            </Alert>
        </div>
    );
}
