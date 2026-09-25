"use client";

import { useState, type FormEvent } from "react";
import { AlertCircle, ContactRound, Loader2, Search, ShieldCheck } from "lucide-react";

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

type EmployeeLookupResponse = {
    ok: boolean;
    employee: CdasEmployee;
};

const DETAILS: Array<{ key: keyof CdasEmployee; label: string }> = [
    { key: "EmployeeNo", label: "Employee number" },
    { key: "Name", label: "Name" },
    { key: "Surname", label: "Surname" },
    { key: "DOB", label: "Date of birth" },
    { key: "Department", label: "Department" },
    { key: "JoiningDate", label: "Joining date" },
    { key: "TerminationDate", label: "Termination date" },
];

export default function CdasEmployeeVerificationPage() {
    const [employeeNo, setEmployeeNo] = useState("");
    const [employee, setEmployee] = useState<CdasEmployee | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function verifyEmployee(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const normalized = employeeNo.trim();
        if (!normalized || loading) return;

        setLoading(true);
        setError(null);
        setEmployee(null);
        try {
            const response = await api.post<EmployeeLookupResponse>("/cdas/employees/verify", {
                employee_no: normalized,
            });
            setEmployee(response.data.employee);
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "CDAS employee verification failed."));
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="loanhub-page space-y-5 2xl:space-y-6">
            <section className="rounded-2xl border bg-card p-5 shadow-sm 2xl:rounded-3xl 2xl:p-7">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="max-w-3xl">
                        <Badge variant="secondary" className="mb-3">CDAS reintegration · Phase 2</Badge>
                        <h1 className="flex items-center gap-2 text-2xl font-black tracking-tight sm:text-3xl">
                            <ShieldCheck className="h-7 w-7 text-primary" />
                            Employee verification
                        </h1>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            Verify one employee deliberately against the official CDAS employee-details service.
                            This phase does not run automatic lookups, affordability checks, deduction reads,
                            bookings or background CDAS jobs.
                        </p>
                    </div>
                    <Badge>Manual verification only</Badge>
                </div>
            </section>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <ContactRound className="h-5 w-5" /> Verify employee
                        </CardTitle>
                        <CardDescription>
                            Enter the employee number exactly as it is known by CDAS, then choose Verify Employee.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-5">
                        <form className="space-y-4" onSubmit={verifyEmployee}>
                            <div className="space-y-2">
                                <Label htmlFor="cdas-employee-number">Employee number</Label>
                                <div className="flex flex-col gap-2 sm:flex-row">
                                    <Input
                                        id="cdas-employee-number"
                                        value={employeeNo}
                                        disabled={loading}
                                        onChange={(event) => {
                                            setEmployeeNo(event.target.value);
                                            setEmployee(null);
                                            setError(null);
                                        }}
                                        placeholder="Enter CDAS employee number"
                                        autoComplete="off"
                                    />
                                    <Button type="submit" disabled={loading || !employeeNo.trim()} className="sm:min-w-44">
                                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                                        {loading ? "Verifying…" : "Verify Employee"}
                                    </Button>
                                </div>
                            </div>
                        </form>

                        {error && (
                            <Alert variant="destructive">
                                <AlertCircle className="h-4 w-4" />
                                <AlertTitle>Verification unsuccessful</AlertTitle>
                                <AlertDescription>{error}</AlertDescription>
                            </Alert>
                        )}

                        {employee && (
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
                                <dl className="grid gap-px bg-border sm:grid-cols-2">
                                    {DETAILS.map(({ key, label }) => (
                                        <div key={key} className="bg-card p-4">
                                            <dt className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{label}</dt>
                                            <dd className="mt-1 break-words text-sm font-bold">{employee[key] || "—"}</dd>
                                        </div>
                                    ))}
                                </dl>
                            </div>
                        )}
                    </CardContent>
                </Card>

                <div className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Phase 2 boundary</CardTitle>
                            <CardDescription>Only employee identification is enabled here.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3 text-sm text-muted-foreground">
                            <p>Each click performs one deliberate employee-details request after CDAS authentication.</p>
                            <p>LoanHub does not query CDAS while you type, open this page or refresh another dashboard.</p>
                            <p>Affordability and deduction functions remain disabled until their own phases are implemented and tested.</p>
                        </CardContent>
                    </Card>

                    <Alert>
                        <AlertCircle className="h-4 w-4" />
                        <AlertTitle>CDAS request limit</AlertTitle>
                        <AlertDescription>
                            The provider documentation specifies a maximum of 400 requests per day per API user.
                            Verify only when the employee information is needed for a lending workflow.
                        </AlertDescription>
                    </Alert>
                </div>
            </div>
        </div>
    );
}
