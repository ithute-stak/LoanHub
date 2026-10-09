"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2, ShieldAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { professionalApi } from "@/api/professional";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, hasRole } from "@/types/auth";
import type { DirectLoanApplication } from "@/types/professional";
import { getErrorMessage } from "@/utils/apiError";

type ProviderRecord = Record<string, unknown>;
type MutationResponse = { ok: boolean; deduction: ProviderRecord };
type LinkedCdasState = {
    loan_id: string;
    mandate_id: string;
    mandate_status: string;
    employee_no: string;
    monthly_deduction: string;
    expected_installments: number;
    deduction_id: number | null;
    item_code: string;
    reference_no: string;
    loan_policy: number;
    principal_amount: string;
    effective_month: string;
    cdas_status: number | null;
    lifecycle_status: string;
    requires_reconciliation: boolean;
    last_request_type: number | null;
    last_synced_at: string | null;
};

type RegistrationDraftResponse = {
    loan_id: string;
    loan_reference: string;
    ready: boolean;
    reasons: string[];
    provider_request_sent: false;
    registration: {
        request_type: 1;
        deduction_id: 0;
        employee_no: string;
        loan_policy: 1;
        item_code: string;
        deduction_amount: string;
        total_installment: number;
        principal_amount: string;
        effective_month: string;
        reference_no: string;
    } | null;
};

const LIFECYCLE_TYPES = [
    [1, "Registration"],
    [3, "Review"],
    [4, "Approve"],
    [6, "Cancel / Reject"],
    [10, "Change / Update"],
] as const;

const LOAN_POLICY_TYPES = [
    [1, "Loan"],
    [2, "Policy"],
] as const;

const SETTLEMENT_REASONS = [
    [1, "Policy Expired"],
    [2, "Paid By Employee"],
    [3, "Consolidation"],
    [4, "Deceased Employee"],
] as const;

function displayValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
}

function generatedExpiryMonth(effectiveMonth: string, period: number): string {
    const match = effectiveMonth.match(/^(\d{4})-(\d{2})$/);
    if (!match || !Number.isInteger(period) || period <= 0) return "Auto-generated";
    const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1 + period - 1, 1));
    return new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric", timeZone: "UTC" }).format(date);
}

function nextEffectiveMonth(): string {
    const now = new Date();
    const date = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1));
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}


function ResultCard({ title, record }: { title: string; record: ProviderRecord }) {
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

export default function CdasOperationsPage() {
    const searchParams = useSearchParams();
    const requestedAction = searchParams.get("action") || "";
    const requestedEmployeeNo = (searchParams.get("employee") || "").trim();
    const isRegisterMode = requestedAction === "register" || requestedAction === "";
    const initialLifecycleType = requestedAction === "review"
        ? 3
        : requestedAction === "approve"
            ? 4
            : requestedAction === "cancel"
                ? 6
                : requestedAction === "change"
                    ? 10
                    : 1;
    const { activeRole } = useTenant();
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const [loading, setLoading] = useState<"prepare" | "lifecycle" | "modify" | "settle" | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<{ title: string; record: ProviderRecord } | null>(null);
    const [approvedCdasApplications, setApprovedCdasApplications] = useState<DirectLoanApplication[]>([]);
    const [selectedLoanId, setSelectedLoanId] = useState(() => searchParams.get("loan") || "");
    const [directEmployeeNo, setDirectEmployeeNo] = useState(requestedEmployeeNo);
    const [registrationDraft, setRegistrationDraft] = useState<RegistrationDraftResponse | null>(null);
    const [borrowerConsentConfirmed, setBorrowerConsentConfirmed] = useState(false);
    const [linkedState, setLinkedState] = useState<LinkedCdasState | null>(null);

    const [lifecycle, setLifecycle] = useState({
        request_type: initialLifecycleType,
        deduction_id: 0,
        employee_no: requestedEmployeeNo,
        loan_policy: 1,
        item_code: "",
        deduction_amount: 0,
        total_installment: 0,
        principal_amount: 0,
        effective_month: "",
        reference_no: "",
        confirmed: false,
    });

    const [modify, setModify] = useState({
        employee_no: "",
        item_code: "",
        total_installment: 1,
        deduction_amount: 0,
        principal_amount: 0,
        deduction_id: 0,
        effective_date: "",
        confirmed: false,
    });

    const [settle, setSettle] = useState({
        item_code: "",
        deduction_id: 0,
        effective_date: "",
        employee_no: "",
        settlement_reason: 2,
        confirmed: false,
    });

    async function loadApprovedCdasLoans() {
        if (loading) return;
        setLoading("prepare");
        setError(null);
        setRegistrationDraft(null);
        try {
            const applications = await professionalApi.listDirect();
            const eligible = applications.filter(
                (application) =>
                    application.status === "approved"
                    && application.cdas_collection_enabled
                    && Boolean(application.loan_id),
            );
            setApprovedCdasApplications(eligible);
            setSelectedLoanId((current) => current || eligible[0]?.loan_id || "");
            if (eligible.length === 0) {
                setError("No approved CDAS-enabled loans are available for registration.");
            }
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "Approved CDAS-enabled loans could not be loaded."));
        } finally {
            setLoading(null);
        }
    }

    async function loadLinkedState() {
        if (!canManage || loading || !selectedLoanId) return;
        setLoading("prepare");
        setError(null);
        try {
            const response = await api.get<LinkedCdasState>(`/cdas/loans/${selectedLoanId}/state`);
            setLinkedState(response.data);
            setLifecycle((current) => ({
                ...current,
                deduction_id: response.data.deduction_id ?? 0,
                employee_no: response.data.employee_no,
                loan_policy: response.data.loan_policy,
                item_code: response.data.item_code,
                deduction_amount: Number(response.data.monthly_deduction),
                total_installment: response.data.expected_installments,
                principal_amount: Number(response.data.principal_amount),
                effective_month: response.data.effective_month,
                reference_no: response.data.reference_no,
                confirmed: false,
            }));
            setModify((current) => ({
                ...current,
                employee_no: response.data.employee_no,
                item_code: response.data.item_code,
                total_installment: response.data.expected_installments,
                deduction_amount: Number(response.data.monthly_deduction),
                principal_amount: Number(response.data.principal_amount),
                deduction_id: response.data.deduction_id ?? 0,
                confirmed: false,
            }));
            setSettle((current) => ({
                ...current,
                item_code: response.data.item_code,
                deduction_id: response.data.deduction_id ?? 0,
                employee_no: response.data.employee_no,
                confirmed: false,
            }));
        } catch (requestError: unknown) {
            setLinkedState(null);
            setError(getErrorMessage(requestError, "Linked CDAS state could not be loaded."));
        } finally {
            setLoading(null);
        }
    }

    async function prepareRegistration() {
        if (!canManage || loading || !selectedLoanId) return;
        setLoading("prepare");
        setError(null);
        setRegistrationDraft(null);
        try {
            const response = await api.get<RegistrationDraftResponse>(
                `/cdas/loans/${selectedLoanId}/registration-draft`,
            );
            setRegistrationDraft(response.data);
            if (!response.data.ready || !response.data.registration) {
                setError(response.data.reasons.join(" ") || "This loan is not ready for CDAS registration.");
                return;
            }
            const draft = response.data.registration;
            setLifecycle({
                request_type: draft.request_type,
                deduction_id: draft.deduction_id,
                employee_no: draft.employee_no,
                loan_policy: draft.loan_policy,
                item_code: draft.item_code,
                deduction_amount: Number(draft.deduction_amount),
                total_installment: draft.total_installment,
                principal_amount: Number(draft.principal_amount),
                effective_month: draft.effective_month,
                reference_no: draft.reference_no,
                confirmed: false,
            });
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS registration preparation failed."));
        } finally {
            setLoading(null);
        }
    }

    async function submitLifecycle(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canManage || loading || !lifecycle.confirmed) return;
        setLoading("lifecycle");
        setError(null);
        setResult(null);
        try {
            const response = (
                lifecycle.request_type === 1 && selectedLoanId && registrationDraft?.ready
                    ? await api.post<MutationResponse>(`/cdas/loans/${selectedLoanId}/register`, {
                        deduction_amount: lifecycle.deduction_amount,
                        deduction_period: lifecycle.total_installment,
                        confirmed: lifecycle.confirmed,
                        borrower_consent: borrowerConsentConfirmed,
                    })
                    : lifecycle.request_type === 1 && directEmployeeNo.trim()
                        ? await api.post<MutationResponse>("/cdas/deductions/direct-register", {
                            employee_no: directEmployeeNo.trim(),
                            deduction_amount: lifecycle.deduction_amount,
                            deduction_period: lifecycle.total_installment,
                            authorization_confirmed: borrowerConsentConfirmed,
                            confirmed: lifecycle.confirmed,
                        })
                    : selectedLoanId && linkedState && [3, 4, 6, 10].includes(lifecycle.request_type)
                        ? await api.post<MutationResponse>(`/cdas/loans/${selectedLoanId}/lifecycle`, {
                            request_type: lifecycle.request_type,
                            confirmed: lifecycle.confirmed,
                        })
                        : await api.post<MutationResponse>("/cdas/deductions/lifecycle", lifecycle)
            );
            setResult({ title: "CDAS lifecycle response", record: response.data.deduction });
            setLifecycle((current) => ({ ...current, confirmed: false }));
            if (lifecycle.request_type === 1) setBorrowerConsentConfirmed(false);
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS deduction lifecycle request failed."));
        } finally {
            setLoading(null);
        }
    }

    async function submitModify(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canManage || loading || !modify.confirmed) return;
        setLoading("modify");
        setError(null);
        setResult(null);
        try {
            const response = (
                selectedLoanId && linkedState
                    ? await api.post<MutationResponse>(`/cdas/loans/${selectedLoanId}/modify-active`, {
                        total_installment: modify.total_installment,
                        deduction_amount: modify.deduction_amount,
                        principal_amount: modify.principal_amount,
                        effective_date: modify.effective_date,
                        confirmed: modify.confirmed,
                    })
                    : await api.post<MutationResponse>("/cdas/deductions/modify-active", modify)
            );
            setResult({ title: "CDAS active-deduction response", record: response.data.deduction });
            setModify((current) => ({ ...current, confirmed: false }));
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS active deduction modification failed."));
        } finally {
            setLoading(null);
        }
    }

    async function submitSettlement(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canManage || loading || !settle.confirmed) return;
        setLoading("settle");
        setError(null);
        setResult(null);
        try {
            const response = (
                selectedLoanId && linkedState
                    ? await api.post<MutationResponse>(`/cdas/loans/${selectedLoanId}/settle`, {
                        effective_date: settle.effective_date,
                        settlement_reason: settle.settlement_reason,
                        confirmed: settle.confirmed,
                    })
                    : await api.post<MutationResponse>("/cdas/deductions/settle", settle)
            );
            setResult({ title: "CDAS settlement response", record: response.data.deduction });
            setSettle((current) => ({ ...current, confirmed: false }));
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS deduction settlement failed."));
        } finally {
            setLoading(null);
        }
    }

    const selectedApplication = approvedCdasApplications.find(
        (application) => application.loan_id === selectedLoanId,
    ) ?? null;

    if (!canManage) {
        return (
            <div className="loanhub-page space-y-5">
                <Button asChild variant="ghost"><Link href="/company/cdas"><ArrowLeft className="h-4 w-4" /> Back to CDAS workspace</Link></Button>
                <Alert variant="destructive">
                    <ShieldAlert className="h-4 w-4" />
                    <AlertTitle>Company management permission required</AlertTitle>
                    <AlertDescription>
                        CDAS deduction state changes are restricted to the company owner or company administrator.
                    </AlertDescription>
                </Alert>
            </div>
        );
    }

    return (
        <div className="loanhub-page space-y-5 2xl:space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <Button asChild variant="ghost"><Link href="/company/cdas"><ArrowLeft className="h-4 w-4" /> Back to CDAS workspace</Link></Button>
                <Badge variant="destructive">State-changing CDAS actions</Badge>
            </div>

            <section className="rounded-2xl border border-destructive/30 bg-card p-5 shadow-sm 2xl:rounded-3xl 2xl:p-7">
                <h1 className="flex items-center gap-2 text-2xl font-black tracking-tight sm:text-3xl">
                    <ShieldAlert className="h-7 w-7 text-destructive" /> {isRegisterMode ? "Add Deduction" : "CDAS deduction operations"}
                </h1>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground">
                    {isRegisterMode
                        ? "Create a new payroll deduction using the same business flow as CDAS, but with LoanHub generating the technical fields automatically."
                        : "These forms change government payroll-deduction state. LoanHub sends a request only after a company owner or administrator completes the form and explicitly confirms the action. No operation runs automatically."}
                </p>
            </section>

            <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Verify the CDAS record before changing it</AlertTitle>
                <AlertDescription>
                    Use the read-only CDAS workspace first to verify the employee, affordability and current deduction. Provider errors such as affordability overflow or disallowed active/approved modification are returned without being hidden.
                </AlertDescription>
            </Alert>

            {error && (
                <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle>CDAS operation unsuccessful</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}


            <Card>
                <CardHeader>
                    <CardTitle>Choose employee or approved LoanHub loan</CardTitle>
                    <CardDescription>
                        Add a deduction directly with an employee number, or select an approved CDAS-enabled LoanHub loan to populate the employee and loan details automatically.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                    <div className="grid gap-4 lg:grid-cols-2">
                        <div className="space-y-2">
                            <Label htmlFor="cdas-direct-employee">Employee number</Label>
                            <Input
                                id="cdas-direct-employee"
                                value={directEmployeeNo}
                                onChange={(event) => {
                                    const value = event.target.value;
                                    setDirectEmployeeNo(value);
                                    if (value.trim()) {
                                        setSelectedLoanId("");
                                        setRegistrationDraft(null);
                                        setLifecycle((current) => ({ ...current, employee_no: value.trim(), principal_amount: 0, effective_month: "", reference_no: "" }));
                                    }
                                }}
                                placeholder="e.g. 0019634"
                                disabled={Boolean(loading)}
                            />
                            <p className="text-xs text-muted-foreground">
                                {requestedEmployeeNo
                                    ? "Loaded from the employee already open in the CDAS workspace."
                                    : "Use this when you want to add a deduction directly for a CDAS employee."}
                            </p>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="cdas-registration-loan">Approved CDAS-enabled loan (optional)</Label>
                            <div className="flex gap-2">
                                <select
                                    id="cdas-registration-loan"
                                    value={selectedLoanId}
                                    disabled={Boolean(loading)}
                                    onChange={(event) => {
                                        const loanId = event.target.value;
                                        setSelectedLoanId(loanId);
                                        setRegistrationDraft(null);
                                        setLinkedState(null);
                                        if (loanId) setDirectEmployeeNo("");
                                    }}
                                    className="h-10 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm"
                                >
                                    <option value="">Select a loan</option>
                                    {approvedCdasApplications.map((application) => (
                                        <option key={application.id} value={application.loan_id || ""}>
                                            {application.loan_reference || application.application_reference} · {application.borrower_name}
                                        </option>
                                    ))}
                                </select>
                                <Button type="button" variant="outline" disabled={Boolean(loading)} onClick={() => void loadApprovedCdasLoans()}>
                                    {loading === "prepare" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                                    Load
                                </Button>
                            </div>
                        </div>
                    </div>

                    {selectedLoanId ? (
                        <div className="flex flex-wrap gap-2">
                            <Button type="button" disabled={Boolean(loading)} onClick={() => void prepareRegistration()}>
                                Prepare selected loan
                            </Button>
                            <Button type="button" variant="outline" disabled={Boolean(loading)} onClick={() => void loadLinkedState()}>
                                Load linked state
                            </Button>
                        </div>
                    ) : null}

                    {registrationDraft ? (
                        <Alert>
                            <CheckCircle2 className="h-4 w-4" />
                            <AlertTitle>{registrationDraft.ready ? "Registration prepared" : "Loan is not ready"}</AlertTitle>
                            <AlertDescription>
                                {registrationDraft.ready
                                    ? `Loan ${registrationDraft.loan_reference} has been copied into the deduction form below. No CDAS request has been sent.`
                                    : registrationDraft.reasons.join(" ")}
                            </AlertDescription>
                        </Alert>
                    ) : null}
                    {linkedState ? (
                        <Alert>
                            <CheckCircle2 className="h-4 w-4" />
                            <AlertTitle>Linked CDAS state loaded</AlertTitle>
                            <AlertDescription>
                                DeductionID {linkedState.deduction_id ?? "pending"} · {linkedState.lifecycle_status}
                                {linkedState.requires_reconciliation ? " · reconciliation required before another lifecycle change" : ""}
                            </AlertDescription>
                        </Alert>
                    ) : null}
                </CardContent>
            </Card>

            <Card id="lifecycle" className="scroll-mt-24 overflow-hidden">
                <CardHeader className="border-b bg-muted/20">
                    <CardTitle>{isRegisterMode ? "New Deduction Application" : "Manage CDAS lifecycle"}</CardTitle>
                    <CardDescription>
                        {isRegisterMode
                            ? "LoanHub follows the CDAS Add Deduction layout, while generating provider identifiers and loan values from the verified approved loan."
                            : "Existing deductions use the documented CDAS lifecycle controls. LoanPolicy is restricted to the documented codes: 1 for Loan and 2 for Policy. The CDAS document assigns code 6 to both Cancelled and Reject; LoanHub preserves that documented ambiguity rather than inventing a new code."}
                    </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                    <form onSubmit={submitLifecycle}>
                        {isRegisterMode ? (
                            <div className="grid lg:grid-cols-[320px_minmax(0,1fr)]">
                                <aside className="border-b bg-muted/15 p-5 lg:border-b-0 lg:border-r">
                                    <p className="mb-4 text-sm font-black">Employee / Loan</p>
                                    <dl className="space-y-3 text-sm">
                                        <div className="grid grid-cols-[120px_1fr] gap-3">
                                            <dt className="text-muted-foreground">Employee No</dt>
                                            <dd className="font-bold">{lifecycle.employee_no || directEmployeeNo.trim() || "Enter employee number"}</dd>
                                        </div>
                                        <div className="grid grid-cols-[120px_1fr] gap-3">
                                            <dt className="text-muted-foreground">Borrower</dt>
                                            <dd className="font-bold">{selectedApplication?.borrower_name || (directEmployeeNo.trim() ? "Direct CDAS employee" : "—")}</dd>
                                        </div>
                                        <div className="grid grid-cols-[120px_1fr] gap-3">
                                            <dt className="text-muted-foreground">Loan reference</dt>
                                            <dd className="break-all font-bold">{registrationDraft?.loan_reference || selectedApplication?.loan_reference || (directEmployeeNo.trim() ? "Auto-generated on registration" : "—")}</dd>
                                        </div>
                                        <div className="grid grid-cols-[120px_1fr] gap-3">
                                            <dt className="text-muted-foreground">Principal</dt>
                                            <dd className="font-bold">
                                                {lifecycle.principal_amount > 0
                                                    ? `M ${lifecycle.principal_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                                                    : directEmployeeNo.trim() && lifecycle.deduction_amount > 0 && lifecycle.total_installment > 0
                                                        ? `M ${(lifecycle.deduction_amount * lifecycle.total_installment).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                                                        : "Auto-generated"}
                                            </dd>
                                        </div>
                                        <div className="mt-5 rounded-xl border bg-card p-3">
                                            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Registration status</p>
                                            <p className="mt-1 font-black">
                                                {registrationDraft?.ready || directEmployeeNo.trim() ? "Ready for deduction capture" : "Enter an employee number or prepare an approved loan"}
                                            </p>
                                        </div>
                                    </dl>
                                </aside>

                                <section className="p-5 sm:p-6">
                                    <div className="space-y-6">
                                        <div>
                                            <div className="mb-3 border-b pb-2">
                                                <p className="text-sm font-black">Agency</p>
                                            </div>
                                            <div className="grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)] sm:items-center">
                                                <Label>Agency / Item Code</Label>
                                                <Input
                                                    value={lifecycle.item_code ? lifecycle.item_code : "Auto-generated from company CDAS profile"}
                                                    readOnly
                                                    className="bg-muted/30 font-semibold"
                                                />
                                            </div>
                                        </div>

                                        <div>
                                            <div className="mb-4 border-b pb-2">
                                                <p className="text-sm font-black">Deduction Details</p>
                                            </div>
                                            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                                                <div className="space-y-2">
                                                    <Label>Deduction Amount *</Label>
                                                    <Input
                                                        type="number"
                                                        min={0.01}
                                                        step="0.01"
                                                        value={lifecycle.deduction_amount}
                                                        onChange={(event) => setLifecycle((value) => ({
                                                            ...value,
                                                            deduction_amount: Number(event.target.value),
                                                        }))}
                                                        disabled={!registrationDraft?.ready && !directEmployeeNo.trim()}
                                                        placeholder="Enter amount"
                                                    />
                                                </div>

                                                <div className="space-y-2">
                                                    <Label>No. of Months *</Label>
                                                    <Input
                                                        type="number"
                                                        min={1}
                                                        max={600}
                                                        value={lifecycle.total_installment}
                                                        onChange={(event) => setLifecycle((value) => ({
                                                            ...value,
                                                            total_installment: Number(event.target.value),
                                                        }))}
                                                        disabled={!registrationDraft?.ready && !directEmployeeNo.trim()}
                                                        placeholder="Enter months"
                                                    />
                                                </div>

                                                <div className="space-y-2">
                                                    <Label>Principal Amt.</Label>
                                                    <Input
                                                        value={lifecycle.principal_amount > 0
                                                            ? lifecycle.principal_amount.toFixed(2)
                                                            : directEmployeeNo.trim() && lifecycle.deduction_amount > 0 && lifecycle.total_installment > 0
                                                                ? (lifecycle.deduction_amount * lifecycle.total_installment).toFixed(2)
                                                                : ""}
                                                        readOnly
                                                        className="bg-muted/30"
                                                        placeholder="Auto-generated"
                                                    />
                                                </div>

                                                <div className="space-y-2">
                                                    <Label>Effective Month</Label>
                                                    <Input
                                                        value={lifecycle.effective_month || (directEmployeeNo.trim() ? nextEffectiveMonth() : "")}
                                                        readOnly
                                                        className="bg-muted/30"
                                                        placeholder="Auto-generated"
                                                    />
                                                </div>

                                                <div className="space-y-2">
                                                    <Label>Expiry Month</Label>
                                                    <Input
                                                        value={generatedExpiryMonth(lifecycle.effective_month || (directEmployeeNo.trim() ? nextEffectiveMonth() : ""), lifecycle.total_installment)}
                                                        readOnly
                                                        className="bg-muted/30"
                                                    />
                                                </div>

                                                <div className="space-y-2">
                                                    <Label>Policy / Loan Ref No</Label>
                                                    <Input
                                                        value={lifecycle.reference_no || (directEmployeeNo.trim() ? "Auto-generated on registration" : "")}
                                                        readOnly
                                                        className="bg-muted/30"
                                                        placeholder="Auto-generated"
                                                    />
                                                </div>
                                            </div>
                                        </div>

                                        {registrationDraft?.ready || directEmployeeNo.trim() ? (
                                            <label className="flex items-start gap-3 rounded-xl border p-4 text-sm">
                                                <input
                                                    type="checkbox"
                                                    checked={borrowerConsentConfirmed}
                                                    onChange={(event) => setBorrowerConsentConfirmed(event.target.checked)}
                                                    className="mt-1"
                                                />
                                                <span>
                                                    <strong>I confirm this employee authorised the payroll deduction.</strong>
                                                    <br />
                                                    <span className="text-muted-foreground">
                                                        LoanHub records this confirmation before the CDAS registration is sent.
                                                    </span>
                                                </span>
                                            </label>
                                        ) : null}

                                        <label className="flex items-start gap-3 rounded-xl border border-destructive/30 p-4 text-sm">
                                            <input
                                                type="checkbox"
                                                checked={lifecycle.confirmed}
                                                onChange={(event) => setLifecycle((value) => ({ ...value, confirmed: event.target.checked }))}
                                                className="mt-1"
                                            />
                                            <span>
                                                <strong>I confirm this new deduction application.</strong>
                                                <br />
                                                <span className="text-muted-foreground">
                                                    I have reviewed the generated employee, agency and loan details before sending this payroll deduction to CDAS.
                                                </span>
                                            </span>
                                        </label>

                                        <div className="flex flex-wrap justify-end gap-2 border-t pt-4">
                                            <Button asChild type="button" variant="outline">
                                                <Link href="/company/cdas">Close</Link>
                                            </Button>
                                            <Button
                                                type="submit"
                                                variant="destructive"
                                                disabled={
                                                    Boolean(loading)
                                                    || (!registrationDraft?.ready && !directEmployeeNo.trim())
                                                    || lifecycle.deduction_amount <= 0
                                                    || lifecycle.total_installment <= 0
                                                    || !borrowerConsentConfirmed
                                                    || !lifecycle.confirmed
                                                }
                                            >
                                                {loading === "lifecycle" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                                                Approve & Register Deduction
                                            </Button>
                                        </div>
                                    </div>
                                </section>
                            </div>
                        ) : (
                            <div className="space-y-5 p-5 sm:p-6">
                                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                                    <div className="space-y-2">
                                        <Label>Request type</Label>
                                        <select value={lifecycle.request_type} onChange={(event) => setLifecycle((v) => ({ ...v, request_type: Number(event.target.value) }))} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                                            {LIFECYCLE_TYPES.map(([value, label]) => <option key={value} value={value}>{value} — {label}</option>)}
                                        </select>
                                    </div>
                                    <div className="space-y-2"><Label>Deduction ID</Label><Input type="number" min={0} value={lifecycle.deduction_id} onChange={(e) => setLifecycle((v) => ({ ...v, deduction_id: Number(e.target.value) }))} /></div>
                                    <div className="space-y-2"><Label>Employee number</Label><Input value={lifecycle.employee_no} onChange={(e) => setLifecycle((v) => ({ ...v, employee_no: e.target.value }))} /></div>
                                    <div className="space-y-2">
                                        <Label>Loan / policy type</Label>
                                        <select value={lifecycle.loan_policy} onChange={(event) => setLifecycle((v) => ({ ...v, loan_policy: Number(event.target.value) }))} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                                            {LOAN_POLICY_TYPES.map(([value, label]) => <option key={value} value={value}>{value} — {label}</option>)}
                                        </select>
                                    </div>
                                    <div className="space-y-2"><Label>Item code</Label><Input value={lifecycle.item_code} onChange={(e) => setLifecycle((v) => ({ ...v, item_code: e.target.value }))} /></div>
                                    <div className="space-y-2"><Label>Deduction amount</Label><Input type="number" min={0} step="0.01" value={lifecycle.deduction_amount} onChange={(e) => setLifecycle((v) => ({ ...v, deduction_amount: Number(e.target.value) }))} /></div>
                                    <div className="space-y-2"><Label>Total instalments</Label><Input type="number" min={0} value={lifecycle.total_installment} onChange={(e) => setLifecycle((v) => ({ ...v, total_installment: Number(e.target.value) }))} /></div>
                                    <div className="space-y-2"><Label>Principal amount</Label><Input type="number" min={0} step="0.01" value={lifecycle.principal_amount} onChange={(e) => setLifecycle((v) => ({ ...v, principal_amount: Number(e.target.value) }))} /></div>
                                    <div className="space-y-2"><Label>Effective month</Label><Input type="month" value={lifecycle.effective_month} onChange={(e) => setLifecycle((v) => ({ ...v, effective_month: e.target.value }))} /></div>
                                    <div className="space-y-2 md:col-span-2 xl:col-span-3"><Label>Reference number</Label><Input value={lifecycle.reference_no} onChange={(e) => setLifecycle((v) => ({ ...v, reference_no: e.target.value }))} /></div>
                                </div>
                                <label className="flex items-start gap-3 rounded-xl border border-destructive/30 p-4 text-sm">
                                    <input type="checkbox" checked={lifecycle.confirmed} onChange={(e) => setLifecycle((v) => ({ ...v, confirmed: e.target.checked }))} className="mt-1" />
                                    <span><strong>I confirm this CDAS lifecycle action.</strong><br /><span className="text-muted-foreground">I have verified the employee and deduction details and understand this request can change the government payroll record.</span></span>
                                </label>
                                <Button type="submit" variant="destructive" disabled={Boolean(loading) || !lifecycle.confirmed}>
                                    {loading === "lifecycle" && <Loader2 className="h-4 w-4 animate-spin" />}
                                    Send Lifecycle Action
                                </Button>
                            </div>
                        )}
                    </form>
                </CardContent>
            </Card>

            {!isRegisterMode ? <Card id="modify-active" className="scroll-mt-24">
                <CardHeader>
                    <CardTitle>Modify active deduction</CardTitle>
                    <CardDescription>Uses the official modify-active-deduction contract. CDAS may reject disallowed active or approved changes.</CardDescription>
                </CardHeader>
                <CardContent>
                    <form className="space-y-5" onSubmit={submitModify}>
                        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                            <div className="space-y-2"><Label>Employee number</Label><Input value={modify.employee_no} onChange={(e) => setModify((v) => ({ ...v, employee_no: e.target.value }))} /></div>
                            <div className="space-y-2"><Label>Item code</Label><Input value={modify.item_code} onChange={(e) => setModify((v) => ({ ...v, item_code: e.target.value }))} /></div>
                            <div className="space-y-2"><Label>Deduction ID</Label><Input type="number" min={0} value={modify.deduction_id} onChange={(e) => setModify((v) => ({ ...v, deduction_id: Number(e.target.value) }))} /></div>
                            <div className="space-y-2"><Label>Total instalments</Label><Input type="number" min={1} value={modify.total_installment} onChange={(e) => setModify((v) => ({ ...v, total_installment: Number(e.target.value) }))} /></div>
                            <div className="space-y-2"><Label>Deduction amount</Label><Input type="number" min={0.01} step="0.01" value={modify.deduction_amount} onChange={(e) => setModify((v) => ({ ...v, deduction_amount: Number(e.target.value) }))} /></div>
                            <div className="space-y-2"><Label>Principal amount</Label><Input type="number" min={0.01} step="0.01" value={modify.principal_amount} onChange={(e) => setModify((v) => ({ ...v, principal_amount: Number(e.target.value) }))} /></div>
                            <div className="space-y-2"><Label>Effective date</Label><Input type="date" value={modify.effective_date} onChange={(e) => setModify((v) => ({ ...v, effective_date: e.target.value }))} /></div>
                        </div>
                        <label className="flex items-start gap-3 rounded-xl border border-destructive/30 p-4 text-sm">
                            <input type="checkbox" checked={modify.confirmed} onChange={(e) => setModify((v) => ({ ...v, confirmed: e.target.checked }))} className="mt-1" />
                            <span><strong>I confirm this active-deduction modification.</strong><br /><span className="text-muted-foreground">The submitted values will be sent to CDAS exactly through the documented operation.</span></span>
                        </label>
                        <Button type="submit" variant="destructive" disabled={Boolean(loading) || !modify.confirmed}>{loading === "modify" && <Loader2 className="h-4 w-4 animate-spin" />} Modify Active Deduction</Button>
                    </form>
                </CardContent>
            </Card> : null}

            <Dialog open={result !== null} onOpenChange={(open) => { if (!open) setResult(null); }}>
                <DialogContent className="sm:max-w-4xl">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-primary" /> CDAS operation completed</DialogTitle>
                        <DialogDescription>
                            The provider response has been recorded in LoanHub&apos;s audit and CDAS operation history.
                        </DialogDescription>
                    </DialogHeader>
                    {result ? <ResultCard title={result.title} record={result.record} /> : null}
                    <DialogFooter showCloseButton>
                        <Button asChild variant="outline">
                            <Link href="/company/cdas/history?tab=transactions">View transaction log</Link>
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {!isRegisterMode ? <Card id="settle" className="scroll-mt-24">
                <CardHeader>
                    <CardTitle>Settle deduction</CardTitle>
                    <CardDescription>Settlement reasons are the four codes documented by CDAS.</CardDescription>
                </CardHeader>
                <CardContent>
                    <form className="space-y-5" onSubmit={submitSettlement}>
                        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                            <div className="space-y-2"><Label>Employee number</Label><Input value={settle.employee_no} onChange={(e) => setSettle((v) => ({ ...v, employee_no: e.target.value }))} /></div>
                            <div className="space-y-2"><Label>Item code</Label><Input value={settle.item_code} onChange={(e) => setSettle((v) => ({ ...v, item_code: e.target.value }))} /></div>
                            <div className="space-y-2"><Label>Deduction ID</Label><Input type="number" min={0} value={settle.deduction_id} onChange={(e) => setSettle((v) => ({ ...v, deduction_id: Number(e.target.value) }))} /></div>
                            <div className="space-y-2 md:col-span-2"><Label>Effective date/time</Label><Input value={settle.effective_date} placeholder="2026-10-01T00:00:00.000Z" onChange={(e) => setSettle((v) => ({ ...v, effective_date: e.target.value }))} /></div>
                            <div className="space-y-2">
                                <Label>Settlement reason</Label>
                                <select value={settle.settlement_reason} onChange={(event) => setSettle((v) => ({ ...v, settlement_reason: Number(event.target.value) }))} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                                    {SETTLEMENT_REASONS.map(([value, label]) => <option key={value} value={value}>{value} — {label}</option>)}
                                </select>
                            </div>
                        </div>
                        <label className="flex items-start gap-3 rounded-xl border border-destructive/30 p-4 text-sm">
                            <input type="checkbox" checked={settle.confirmed} onChange={(e) => setSettle((v) => ({ ...v, confirmed: e.target.checked }))} className="mt-1" />
                            <span><strong>I confirm this deduction settlement.</strong><br /><span className="text-muted-foreground">Settlement is a state-changing action and will be recorded in the LoanHub audit log.</span></span>
                        </label>
                        <Button type="submit" variant="destructive" disabled={Boolean(loading) || !settle.confirmed}>{loading === "settle" && <Loader2 className="h-4 w-4 animate-spin" />} Settle Deduction</Button>
                    </form>
                </CardContent>
            </Card> : null}
        </div>
    );
}
