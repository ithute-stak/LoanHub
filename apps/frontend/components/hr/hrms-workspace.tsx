"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
    Activity,
    BriefcaseBusiness,
    Building2,
    CalendarCheck2,
    ClipboardCheck,
    GraduationCap,
    IdCard,
    Laptop2,
    Loader2,
    Plus,
    RefreshCcw,
    ShieldCheck,
    UsersRound,
    WalletCards,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
    calculateHRPayrollRun,
    createHRAsset,
    createHRDepartment,
    createHRLeaveType,
    createHRPayrollRun,
    createHRPosition,
    createHRTrainingProgram,
    createHRVacancy,
    decideHRLeaveRequest,
    getHRDashboard,
    listHRAttendanceEvents,
    listHRAssets,
    listHRCandidates,
    listHRDepartments,
    listHRLeaveRequests,
    listHRLeaveTypes,
    listHRPayrollRuns,
    listHRPositions,
    listHRShifts,
    listHRTrainingPrograms,
    listHRVacancies,
} from "@/api/hrms";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import type {
    HRAsset,
    HRAttendanceEvent,
    HRCandidate,
    HRDashboardSummary,
    HRDepartment,
    HRLeaveRequest,
    HRLeaveType,
    HRPayrollRun,
    HRPosition,
    HRShift,
    HRTrainingProgram,
    HRVacancy,
} from "@/types/hrms";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";
import { useTenant } from "@/provider/tenantProvider";
import { COMPANY_MANAGEMENT_ROLES, HR_ROLES, PERFORMANCE_ROLES, hasRole } from "@/types/auth";

type HRWorkspaceTab =
    | "overview"
    | "organisation"
    | "attendance"
    | "leave"
    | "payroll"
    | "recruitment"
    | "training"
    | "assets";

const HR_WORKSPACE_TABS = new Set<HRWorkspaceTab>([
    "overview",
    "organisation",
    "attendance",
    "leave",
    "payroll",
    "recruitment",
    "training",
    "assets",
]);

type SafeLoadResult<T> = {
    label: string;
    value: T;
    error: string | null;
};

async function safeLoad<T>(label: string, request: Promise<T>, fallback: T): Promise<SafeLoadResult<T>> {
    try {
        return { label, value: await request, error: null };
    } catch (requestError: unknown) {
        return {
            label,
            value: fallback,
            error: getErrorMessage(requestError, `${label} could not be loaded.`),
        };
    }
}

const EMPTY_SUMMARY: HRDashboardSummary = {
    total_employees: 0,
    active_employees: 0,
    employees_present_today: 0,
    employees_absent_today: 0,
    employees_on_leave_today: 0,
    pending_leave_requests: 0,
    open_vacancies: 0,
    active_training_programs: 0,
    assigned_assets: 0,
    payroll_status: null,
    payroll_net_total: 0,
    departments: 0,
    branches: 0,
};

function titleCase(value: string | null | undefined): string {
    return String(value || "Not started")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function money(value: number | string | null | undefined, currency = "LSL"): string {
    const amount = Number(value || 0);
    return `${currency} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value: string | null | undefined): string {
    if (!value) return "—";
    const parsed = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString();
}

export function HRMSWorkspace() {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const searchQuery = searchParams.toString();
    const { activeRole } = useTenant();
    const requestedTab = searchParams.get("tab") as HRWorkspaceTab | null;
    const preferredTab = requestedTab && HR_WORKSPACE_TABS.has(requestedTab) ? requestedTab : "overview";
    const [summary, setSummary] = useState<HRDashboardSummary>(EMPTY_SUMMARY);
    const [departments, setDepartments] = useState<HRDepartment[]>([]);
    const [positions, setPositions] = useState<HRPosition[]>([]);
    const [shifts, setShifts] = useState<HRShift[]>([]);
    const [attendance, setAttendance] = useState<HRAttendanceEvent[]>([]);
    const [leaveTypes, setLeaveTypes] = useState<HRLeaveType[]>([]);
    const [leaveRequests, setLeaveRequests] = useState<HRLeaveRequest[]>([]);
    const [payrollRuns, setPayrollRuns] = useState<HRPayrollRun[]>([]);
    const [vacancies, setVacancies] = useState<HRVacancy[]>([]);
    const [candidates, setCandidates] = useState<HRCandidate[]>([]);
    const [training, setTraining] = useState<HRTrainingProgram[]>([]);
    const [assets, setAssets] = useState<HRAsset[]>([]);
    const [loading, setLoading] = useState(true);
    const [working, setWorking] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        const today = new Date().toISOString().slice(0, 10);
        const [
            dashboardResult,
            departmentResult,
            positionResult,
            shiftResult,
            attendanceResult,
            leaveTypeResult,
            leaveRequestResult,
            payrollResult,
            vacancyResult,
            candidateResult,
            trainingResult,
            assetResult,
        ] = await Promise.all([
            safeLoad("HR dashboard", getHRDashboard(), EMPTY_SUMMARY),
            safeLoad("Departments", listHRDepartments(), [] as HRDepartment[]),
            safeLoad("Positions", listHRPositions(), [] as HRPosition[]),
            safeLoad("Shifts", listHRShifts(), [] as HRShift[]),
            safeLoad("Attendance", listHRAttendanceEvents({ attendance_date: today }), [] as HRAttendanceEvent[]),
            safeLoad("Leave types", listHRLeaveTypes(), [] as HRLeaveType[]),
            safeLoad("Leave requests", listHRLeaveRequests(), [] as HRLeaveRequest[]),
            safeLoad("Payroll", listHRPayrollRuns(), [] as HRPayrollRun[]),
            safeLoad("Vacancies", listHRVacancies(), [] as HRVacancy[]),
            safeLoad("Candidates", listHRCandidates(), [] as HRCandidate[]),
            safeLoad("Training", listHRTrainingPrograms(), [] as HRTrainingProgram[]),
            safeLoad("Assets", listHRAssets(), [] as HRAsset[]),
        ]);

        setSummary(dashboardResult.value);
        setDepartments(departmentResult.value);
        setPositions(positionResult.value);
        setShifts(shiftResult.value);
        setAttendance(attendanceResult.value);
        setLeaveTypes(leaveTypeResult.value);
        setLeaveRequests(leaveRequestResult.value);
        setPayrollRuns(payrollResult.value);
        setVacancies(vacancyResult.value);
        setCandidates(candidateResult.value);
        setTraining(trainingResult.value);
        setAssets(assetResult.value);

        const failures = [
            dashboardResult,
            departmentResult,
            positionResult,
            shiftResult,
            attendanceResult,
            leaveTypeResult,
            leaveRequestResult,
            payrollResult,
            vacancyResult,
            candidateResult,
            trainingResult,
            assetResult,
        ].filter((result) => result.error);

        if (failures.length) {
            setError(`Some workforce areas are temporarily unavailable: ${failures.map((result) => result.label).join(", ")}. Available sections remain usable.`);
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    const canManageAccess = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);
    const canManageEmployees = hasRole(activeRole, HR_ROLES);
    const canManagePerformance = hasRole(activeRole, PERFORMANCE_ROLES);

    function selectTab(value: string) {
        const nextTab = HR_WORKSPACE_TABS.has(value as HRWorkspaceTab)
            ? value as HRWorkspaceTab
            : "overview";
        const next = new URLSearchParams(searchQuery);
        if (nextTab === "overview") next.delete("tab");
        else next.set("tab", nextTab);
        const query = next.toString();
        router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    }

    const pendingLeave = useMemo(
        () => leaveRequests.filter((request) => request.status === "pending"),
        [leaveRequests],
    );

    async function runAction(key: string, action: () => Promise<void>, success: string) {
        setWorking(key);
        try {
            await action();
            toast.success(success);
            await load();
        } catch (requestError: unknown) {
            toast.error(getErrorMessage(requestError, "The HR action could not be completed."));
        } finally {
            setWorking(null);
        }
    }

    return (
        <main className="space-y-6 pb-12">
            <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                <div className="absolute -right-24 -top-28 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <div className="mb-3 flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-black uppercase tracking-[0.14em] text-primary">
                                Hybrid workforce module
                            </span>
                            <span className="rounded-full border px-3 py-1 text-xs font-bold text-muted-foreground">
                                Multi-company · Multi-branch
                            </span>
                        </div>
                        <h1 className="text-3xl font-black tracking-tight md:text-4xl">
                            Workforce & Human Resources
                        </h1>
                        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground md:text-base">
                            Coordinate staff access, employee records, organisation, attendance, leave, payroll, recruitment, performance, training and company assets from one secure command centre.
                        </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {canManageAccess && (
                            <Button asChild variant="outline" size="lg">
                                <Link href="/company/people?tab=access"><ShieldCheck /> People & access</Link>
                            </Button>
                        )}
                        {canManageEmployees && (
                            <Button asChild variant="outline" size="lg">
                                <Link href="/company/people?tab=employees"><UsersRound /> Employee records</Link>
                            </Button>
                        )}
                        {canManagePerformance && (
                            <Button asChild variant="outline" size="lg">
                                <Link href="/company/performance"><ClipboardCheck /> Performance</Link>
                            </Button>
                        )}
                        <Button onClick={() => void load()} disabled={loading} size="lg">
                            <RefreshCcw className={loading ? "animate-spin" : ""} /> Refresh workforce
                        </Button>
                    </div>
                </div>
            </section>

            {error && (
                <div role="status" aria-live="polite" className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm font-semibold text-amber-800 dark:text-amber-200">
                    {error}
                </div>
            )}

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric icon={UsersRound} label="Active employees" value={summary.active_employees} note={`${summary.total_employees} total employee profiles`} />
                <Metric icon={CalendarCheck2} label="Present today" value={summary.employees_present_today} note={`${summary.employees_absent_today} absent · ${summary.employees_on_leave_today} on leave`} />
                <Metric icon={ClipboardCheck} label="Leave approvals" value={summary.pending_leave_requests} note="Requests needing management attention" />
                <Metric icon={WalletCards} label="Latest payroll" value={money(summary.payroll_net_total)} note={titleCase(summary.payroll_status)} />
            </section>

            <Tabs value={preferredTab} onValueChange={selectTab} className="gap-5">
                <StickyFilterBar
                    ariaLabel="Workforce workspace navigation"
                    landmarkRole="navigation"
                    className="rounded-2xl data-[floating=true]:border"
                >
                    <div className="overflow-x-auto rounded-[inherit] border bg-card/95 p-2 backdrop-blur">
                        <TabsList className="h-auto min-w-max bg-transparent">
                            <TabsTrigger value="overview"><ShieldCheck /> Overview</TabsTrigger>
                            <TabsTrigger value="organisation"><Building2 /> Organisation</TabsTrigger>
                            <TabsTrigger value="attendance"><Activity /> Attendance</TabsTrigger>
                            <TabsTrigger value="leave"><CalendarCheck2 /> Leave</TabsTrigger>
                            <TabsTrigger value="payroll"><WalletCards /> Payroll</TabsTrigger>
                            <TabsTrigger value="recruitment"><BriefcaseBusiness /> Recruitment</TabsTrigger>
                            <TabsTrigger value="training"><GraduationCap /> Training</TabsTrigger>
                            <TabsTrigger value="assets"><Laptop2 /> Assets</TabsTrigger>
                        </TabsList>
                    </div>
                </StickyFilterBar>

                <TabsContent value="overview" className="space-y-5">
                    <Card>
                        <CardHeader>
                            <CardTitle>One workforce, four connected control layers</CardTitle>
                            <CardDescription>
                                LoanHub keeps account access, employment records, HR operations and performance connected while preserving separate permissions and audit trails.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                            <HybridLane icon={ShieldCheck} step="01" title="People & access" description="Company membership, role, branch and account activation." href="/company/people?tab=access" enabled={canManageAccess} />
                            <HybridLane icon={IdCard} step="02" title="Employee records" description="Employment profile, manager, contracts and protected details." href="/company/people?tab=employees" enabled={canManageEmployees} />
                            <HybridLane icon={UsersRound} step="03" title="HR operations" description="Attendance, leave, payroll, recruitment, training and assets." href="/company/hr" enabled />
                            <HybridLane icon={ClipboardCheck} step="04" title="Performance" description="Goals, reviews, evidence and fair workforce analytics." href="/company/performance" enabled={canManagePerformance} />
                        </CardContent>
                    </Card>

                    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        {canManageAccess && <ModuleLink icon={ShieldCheck} title="People & access control" description="One person can hold approved roles across branches without duplicating accounts or employment records." href="/company/people?tab=access" status="Role-aware" />}
                        <ModuleLink icon={IdCard} title="Employee management" description="Profiles, employment records, reporting lines, qualifications, contracts and protected HR information." href="/company/people?tab=employees" status={`${summary.active_employees} active`} />
                        <ModuleLink icon={Activity} title="Attendance management" description="Fingerprint, RFID, face, QR, GPS, manual and offline attendance event foundation." href="/company/hr?tab=attendance" status={`${attendance.length} events today`} />
                        <ModuleLink icon={CalendarCheck2} title="Leave management" description="Configurable leave types, employee requests and manager approval workflow." href="/company/hr?tab=leave" status={`${pendingLeave.length} pending`} />
                        <ModuleLink icon={WalletCards} title="Payroll management" description="Controlled payroll periods with calculation, review, approval, payment and locking stages." href="/company/hr?tab=payroll" status={titleCase(summary.payroll_status)} />
                        <ModuleLink icon={BriefcaseBusiness} title="Recruitment" description="Vacancies, candidates and onboarding pipeline for every company and branch." href="/company/hr?tab=recruitment" status={`${summary.open_vacancies} open`} />
                        <ModuleLink icon={GraduationCap} title="Performance & training" description="Existing LoanHub goals and reviews plus training programmes, enrolment and skills development." href="/company/performance" status={`${summary.active_training_programs} programmes`} />
                        <ModuleLink icon={Laptop2} title="Asset management" description="Track laptops, phones, vehicles, uniforms, tools, assignments, returns and condition." href="/company/hr?tab=assets" status={`${summary.assigned_assets} assigned`} />
                        <ModuleLink icon={Building2} title="Organisation structure" description="Branches, departments, positions, cost centres, managers and reporting structures." href="/company/hr?tab=organisation" status={`${summary.departments} departments`} />
                        <ModuleLink icon={ShieldCheck} title="HR reports & security" description="Tenant isolation, branch scope, protected payroll data, audit history and export-ready records." href="/company/reports" status={`${summary.branches} branches`} />
                    </section>

                    <Card>
                        <CardHeader>
                            <CardTitle>Implementation status</CardTitle>
                            <CardDescription>
                                The hybrid module connects existing staff access, employee and performance workspaces to the native HRMS operational APIs without duplicating people or weakening permissions.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <Status label="Employee profiles" state="Connected" />
                            <Status label="Attendance events" state="Active" />
                            <Status label="Leave workflow" state="Active" />
                            <Status label="Payroll lifecycle" state="Foundation" />
                            <Status label="Recruitment pipeline" state="Active" />
                            <Status label="Training register" state="Active" />
                            <Status label="Asset register" state="Active" />
                            <Status label="Biometric devices" state="Integration-ready" />
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="organisation" className="space-y-5" id="organisation">
                    <section className="grid gap-5 xl:grid-cols-2">
                        <CreateDepartmentCard onCreate={(values) => runAction("department", () => createHRDepartment(values).then(() => undefined), "Department created.")} working={working === "department"} />
                        <CreatePositionCard departments={departments} onCreate={(values) => runAction("position", () => createHRPosition(values).then(() => undefined), "Position created.")} working={working === "position"} />
                    </section>
                    <section className="grid gap-5 xl:grid-cols-2">
                        <RecordList title="Departments" description="Company and branch organisation units" empty="No departments have been created.">
                            {departments.map((department) => (
                                <RecordRow key={department.id} title={department.name} subtitle={`${department.code}${department.cost_centre ? ` · ${department.cost_centre}` : ""}`} badge={department.is_active ? "Active" : "Inactive"} />
                            ))}
                        </RecordList>
                        <RecordList title="Positions" description="Job titles, grades and salary bands" empty="No positions have been created.">
                            {positions.map((position) => (
                                <RecordRow key={position.id} title={position.title} subtitle={`${position.code}${position.grade ? ` · Grade ${position.grade}` : ""}`} badge={position.is_active ? "Active" : "Inactive"} />
                            ))}
                        </RecordList>
                    </section>
                </TabsContent>

                <TabsContent value="attendance" className="space-y-5" id="attendance">
                    <section className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
                        <RecordList title="Configured shifts" description="Work schedules and grace periods" empty="No shifts are configured yet.">
                            {shifts.map((shift) => (
                                <RecordRow key={shift.id} title={shift.name} subtitle={`${shift.start_time}–${shift.end_time} · ${shift.break_minutes} min break`} badge={shift.code} />
                            ))}
                        </RecordList>
                        <RecordList title="Today’s attendance events" description="Latest clocking activity from all supported sources" empty="No attendance events have been recorded today.">
                            {attendance.slice(0, 20).map((event) => (
                                <RecordRow key={event.id} title={titleCase(event.event_type)} subtitle={`${new Date(event.occurred_at).toLocaleString()} · ${titleCase(event.source)}`} badge={titleCase(event.status)} />
                            ))}
                        </RecordList>
                    </section>
                    <Card>
                        <CardHeader>
                            <CardTitle>Attendance integrations</CardTitle>
                            <CardDescription>Secured API events can be submitted by manual entry, fingerprint terminals, RFID, face recognition, QR, mobile GPS or offline synchronisation.</CardDescription>
                        </CardHeader>
                        <CardContent className="flex flex-wrap gap-2">
                            {["Fingerprint", "RFID", "Face recognition", "QR code", "Mobile GPS", "Manual", "Offline sync"].map((item) => (
                                <span key={item} className="rounded-full border bg-muted/40 px-3 py-1.5 text-xs font-bold">{item}</span>
                            ))}
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="leave" className="space-y-5" id="leave">
                    <section className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
                        <CreateLeaveTypeCard onCreate={(values) => runAction("leave-type", () => createHRLeaveType(values).then(() => undefined), "Leave type created.")} working={working === "leave-type"} />
                        <RecordList title="Leave types" description="Configurable company leave policies" empty="No leave types have been configured.">
                            {leaveTypes.map((leaveType) => (
                                <RecordRow key={leaveType.id} title={leaveType.name} subtitle={`${leaveType.annual_days} days · ${leaveType.paid ? "Paid" : "Unpaid"}`} badge={leaveType.code} />
                            ))}
                        </RecordList>
                    </section>
                    <RecordList title="Leave requests" description="Employee requests and management decisions" empty="No leave requests are available.">
                        {leaveRequests.map((request) => (
                            <div key={request.id} className="flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center sm:justify-between">
                                <div>
                                    <p className="font-black">{dateLabel(request.start_date)} – {dateLabel(request.end_date)}</p>
                                    <p className="mt-1 text-xs text-muted-foreground">{request.days_requested} day(s) · {request.reason || "No reason supplied"}</p>
                                </div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className="rounded-full border px-3 py-1 text-xs font-black">{titleCase(request.status)}</span>
                                    {request.status === "pending" && (
                                        <>
                                            <Button size="sm" onClick={() => void runAction(`leave-approve-${request.id}`, () => decideHRLeaveRequest(request.id, "approved").then(() => undefined), "Leave approved.")} disabled={working !== null}>Approve</Button>
                                            <Button size="sm" variant="outline" onClick={() => void runAction(`leave-decline-${request.id}`, () => decideHRLeaveRequest(request.id, "declined").then(() => undefined), "Leave declined.")} disabled={working !== null}>Decline</Button>
                                        </>
                                    )}
                                </div>
                            </div>
                        ))}
                    </RecordList>
                </TabsContent>

                <TabsContent value="payroll" className="space-y-5" id="payroll">
                    <section className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
                        <CreatePayrollCard onCreate={(values) => runAction("payroll", () => createHRPayrollRun(values).then(() => undefined), "Payroll period created.")} working={working === "payroll"} />
                        <Card>
                            <CardHeader>
                                <CardTitle>Payroll control lifecycle</CardTitle>
                                <CardDescription>Locked payroll history remains immutable. Corrections must be handled through adjustment entries.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="grid gap-2 sm:grid-cols-3">
                                    {["Draft", "Calculated", "Under review", "Approved", "Paid", "Locked"].map((step, index) => (
                                        <div key={step} className="rounded-xl border bg-muted/30 p-3">
                                            <p className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Step {index + 1}</p>
                                            <p className="mt-1 font-black">{step}</p>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </section>
                    <RecordList title="Payroll runs" description="Salary periods, totals and approval status" empty="No payroll periods have been created.">
                        {payrollRuns.map((run) => (
                            <div key={run.id} className="flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center sm:justify-between">
                                <div>
                                    <p className="font-black">{run.period_key}</p>
                                    <p className="mt-1 text-xs text-muted-foreground">Pay date {dateLabel(run.pay_date)} · Net {money(run.net_total, run.currency)}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="rounded-full border px-3 py-1 text-xs font-black">{titleCase(run.status)}</span>
                                    {run.status === "draft" && (
                                        <Button size="sm" onClick={() => void runAction(`payroll-calc-${run.id}`, () => calculateHRPayrollRun(run.id).then(() => undefined), "Payroll calculated.")} disabled={working !== null}>
                                            Calculate
                                        </Button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </RecordList>
                </TabsContent>

                <TabsContent value="recruitment" className="space-y-5" id="recruitment">
                    <section className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
                        <CreateVacancyCard onCreate={(values) => runAction("vacancy", () => createHRVacancy(values).then(() => undefined), "Vacancy created.")} working={working === "vacancy"} />
                        <RecordList title="Vacancies" description="Openings from draft to closing" empty="No vacancies have been created.">
                            {vacancies.map((vacancy) => (
                                <RecordRow key={vacancy.id} title={vacancy.title} subtitle={`${vacancy.reference} · ${vacancy.openings} opening(s) · closes ${dateLabel(vacancy.closing_date)}`} badge={titleCase(vacancy.status)} />
                            ))}
                        </RecordList>
                    </section>
                    <RecordList title="Candidate database" description="Applicants and recruitment stage" empty="No candidates have been registered.">
                        {candidates.map((candidate) => (
                            <RecordRow key={candidate.id} title={candidate.full_name} subtitle={[candidate.email, candidate.phone].filter(Boolean).join(" · ") || "No contact information"} badge={titleCase(candidate.stage)} />
                        ))}
                    </RecordList>
                </TabsContent>

                <TabsContent value="training" className="space-y-5" id="training">
                    <section className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
                        <CreateTrainingCard onCreate={(values) => runAction("training", () => createHRTrainingProgram(values).then(() => undefined), "Training programme created.")} working={working === "training"} />
                        <RecordList title="Training programmes" description="Courses, capacity, skills and completion status" empty="No training programmes have been created.">
                            {training.map((program) => (
                                <RecordRow key={program.id} title={program.title} subtitle={`${program.provider || "Internal"} · ${dateLabel(program.start_date)} · ${program.skills.join(", ") || "General skills"}`} badge={titleCase(program.status)} />
                            ))}
                        </RecordList>
                    </section>
                    <Card>
                        <CardHeader>
                            <CardTitle>Performance integration</CardTitle>
                            <CardDescription>Use the existing LoanHub performance workspace for goals, KPI tracking, formal reviews and evidence-based promotion recommendations.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Button asChild><Link href="/company/performance">Open performance management</Link></Button>
                        </CardContent>
                    </Card>
                </TabsContent>

                <TabsContent value="assets" className="space-y-5" id="assets">
                    <section className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
                        <CreateAssetCard onCreate={(values) => runAction("asset", () => createHRAsset(values).then(() => undefined), "Company asset created.")} working={working === "asset"} />
                        <RecordList title="Company assets" description="Availability, assignment and condition register" empty="No company assets have been recorded.">
                            {assets.map((asset) => (
                                <RecordRow key={asset.id} title={asset.name} subtitle={`${asset.asset_tag} · ${asset.category} · ${asset.serial_number || "No serial"}`} badge={`${titleCase(asset.status)} · ${titleCase(asset.condition)}`} />
                            ))}
                        </RecordList>
                    </section>
                </TabsContent>
            </Tabs>

            {loading && (
                <div className="fixed inset-x-0 bottom-5 z-50 mx-auto flex w-fit items-center gap-2 rounded-full border bg-background px-4 py-2 text-xs font-bold shadow-lg">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading HRMS records…
                </div>
            )}
        </main>
    );
}

function HybridLane({
    icon: Icon,
    step,
    title,
    description,
    href,
    enabled,
}: {
    icon: typeof UsersRound;
    step: string;
    title: string;
    description: string;
    href: string;
    enabled: boolean;
}) {
    const content = (
        <div className={`h-full rounded-2xl border p-4 transition ${enabled ? "bg-muted/20 hover:border-primary/40 hover:bg-primary/5" : "bg-muted/40 opacity-60"}`}>
            <div className="flex items-center justify-between gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
                <span className="text-xs font-black tracking-[0.16em] text-muted-foreground">{step}</span>
            </div>
            <p className="mt-4 font-black">{title}</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
            {!enabled && <p className="mt-3 text-[11px] font-bold uppercase tracking-wide text-muted-foreground">Not available to this role</p>}
        </div>
    );

    return enabled ? <Link href={href}>{content}</Link> : content;
}

function Metric({ icon: Icon, label, value, note }: { icon: typeof UsersRound; label: string; value: number | string; note: string }) {
    return (
        <Card>
            <CardContent className="flex items-start justify-between gap-4 pt-1">
                <div className="min-w-0">
                    <p className="text-xs font-black uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
                    <p className="mt-2 break-words text-2xl font-black">{value}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{note}</p>
                </div>
                <div className="rounded-2xl bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5" /></div>
            </CardContent>
        </Card>
    );
}

function ModuleLink({ icon: Icon, title, description, href, status }: { icon: typeof UsersRound; title: string; description: string; href: string; status: string }) {
    return (
        <Link href={href} className="group rounded-2xl border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md">
            <div className="flex items-start justify-between gap-4">
                <div className="rounded-2xl bg-primary/10 p-3 text-primary"><Icon className="h-5 w-5" /></div>
                <span className="rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-wider text-muted-foreground">{status}</span>
            </div>
            <h2 className="mt-4 text-lg font-black group-hover:text-primary">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
        </Link>
    );
}

function Status({ label, state }: { label: string; state: string }) {
    return (
        <div className="rounded-xl border bg-muted/20 p-3">
            <p className="text-xs font-bold text-muted-foreground">{label}</p>
            <p className="mt-1 font-black text-primary">{state}</p>
        </div>
    );
}

function RecordList({ title, description, empty, children }: { title: string; description: string; empty: string; children: React.ReactNode }) {
    const childArray = useMemo(() => Array.isArray(children) ? children : [children], [children]);
    const hasChildren = childArray.some(Boolean);
    return (
        <Card>
            <CardHeader>
                <CardTitle>{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                {hasChildren ? children : <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">{empty}</p>}
            </CardContent>
        </Card>
    );
}

function RecordRow({ title, subtitle, badge }: { title: string; subtitle: string; badge: string }) {
    return (
        <div className="flex flex-col gap-2 rounded-2xl border p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
                <p className="truncate font-black">{title}</p>
                <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
            </div>
            <span className="w-fit rounded-full border px-3 py-1 text-xs font-black">{badge}</span>
        </div>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return <label className="space-y-2"><span className="text-xs font-black uppercase tracking-wider text-muted-foreground">{label}</span>{children}</label>;
}

function CreateDepartmentCard({ onCreate, working }: { onCreate: (value: { name: string; code: string; cost_centre: string | null; description: string | null }) => Promise<void>; working: boolean }) {
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        await onCreate({
            name: String(data.get("name") || "").trim(),
            code: String(data.get("code") || "").trim().toUpperCase(),
            cost_centre: String(data.get("cost_centre") || "").trim() || null,
            description: String(data.get("description") || "").trim() || null,
        });
        event.currentTarget.reset();
    }
    return <FormCard title="Create department" description="Build the company’s branch, department and cost-centre structure" onSubmit={submit} working={working}>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Department name"><Input name="name" required /></Field><Field label="Code"><Input name="code" required /></Field></div>
        <Field label="Cost centre"><Input name="cost_centre" /></Field><Field label="Description"><Textarea name="description" /></Field>
    </FormCard>;
}

function CreatePositionCard({ departments, onCreate, working }: { departments: HRDepartment[]; onCreate: (value: { title: string; code: string; department_id: string | null; grade: string | null; currency: string }) => Promise<void>; working: boolean }) {
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        await onCreate({ title: String(data.get("title") || "").trim(), code: String(data.get("code") || "").trim().toUpperCase(), department_id: String(data.get("department_id") || "") || null, grade: String(data.get("grade") || "").trim() || null, currency: "LSL" });
        event.currentTarget.reset();
    }
    return <FormCard title="Create position" description="Define job titles, grades and reporting structure" onSubmit={submit} working={working}>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Position title"><Input name="title" required /></Field><Field label="Code"><Input name="code" required /></Field></div>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Department"><NativeSelect name="department_id"><option value="">Unassigned</option>{departments.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</NativeSelect></Field><Field label="Grade"><Input name="grade" /></Field></div>
    </FormCard>;
}

function CreateLeaveTypeCard({ onCreate, working }: { onCreate: (value: { name: string; code: string; paid: boolean; annual_days: number; requires_attachment: boolean; approval_levels: number }) => Promise<void>; working: boolean }) {
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        await onCreate({ name: String(data.get("name") || "").trim(), code: String(data.get("code") || "").trim().toUpperCase(), paid: data.get("paid") === "true", annual_days: Number(data.get("annual_days") || 0), requires_attachment: data.get("requires_attachment") === "true", approval_levels: Number(data.get("approval_levels") || 1) });
        event.currentTarget.reset();
    }
    return <FormCard title="Create leave type" description="Annual, sick, maternity, compassionate, study, unpaid and company-specific leave" onSubmit={submit} working={working}>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Leave name"><Input name="name" required /></Field><Field label="Code"><Input name="code" required /></Field></div>
        <div className="grid gap-4 sm:grid-cols-3"><Field label="Annual days"><Input name="annual_days" type="number" min="0" defaultValue="0" /></Field><Field label="Paid"><NativeSelect name="paid" defaultValue="true"><option value="true">Yes</option><option value="false">No</option></NativeSelect></Field><Field label="Approval levels"><Input name="approval_levels" type="number" min="1" max="5" defaultValue="1" /></Field></div>
        <Field label="Attachment required"><NativeSelect name="requires_attachment" defaultValue="false"><option value="false">No</option><option value="true">Yes</option></NativeSelect></Field>
    </FormCard>;
}

function CreatePayrollCard({ onCreate, working }: { onCreate: (value: { period_key: string; period_start: string; period_end: string; pay_date: string; currency: string }) => Promise<void>; working: boolean }) {
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        await onCreate({ period_key: String(data.get("period_key") || "").trim(), period_start: String(data.get("period_start") || ""), period_end: String(data.get("period_end") || ""), pay_date: String(data.get("pay_date") || ""), currency: "LSL" });
        event.currentTarget.reset();
    }
    return <FormCard title="Create payroll period" description="Start a controlled salary run for the selected month or period" onSubmit={submit} working={working}>
        <Field label="Period key"><Input name="period_key" placeholder="2026-08" required /></Field>
        <div className="grid gap-4 sm:grid-cols-3"><Field label="Start"><Input name="period_start" type="date" required /></Field><Field label="End"><Input name="period_end" type="date" required /></Field><Field label="Pay date"><Input name="pay_date" type="date" required /></Field></div>
    </FormCard>;
}

function CreateVacancyCard({ onCreate, working }: { onCreate: (value: { title: string; reference: string; description: string | null; openings: number; status: "draft" | "published" | "closed" | "cancelled"; closing_date: string | null }) => Promise<void>; working: boolean }) {
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        await onCreate({ title: String(data.get("title") || "").trim(), reference: String(data.get("reference") || "").trim().toUpperCase(), description: String(data.get("description") || "").trim() || null, openings: Number(data.get("openings") || 1), status: String(data.get("status") || "draft") as "draft" | "published" | "closed" | "cancelled", closing_date: String(data.get("closing_date") || "") || null });
        event.currentTarget.reset();
    }
    return <FormCard title="Create vacancy" description="Manage hiring from vacancy posting through candidate onboarding" onSubmit={submit} working={working}>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Vacancy title"><Input name="title" required /></Field><Field label="Reference"><Input name="reference" required /></Field></div>
        <div className="grid gap-4 sm:grid-cols-3"><Field label="Openings"><Input name="openings" type="number" min="1" defaultValue="1" /></Field><Field label="Status"><NativeSelect name="status" defaultValue="draft"><option value="draft">Draft</option><option value="published">Published</option><option value="closed">Closed</option></NativeSelect></Field><Field label="Closing date"><Input name="closing_date" type="date" /></Field></div>
        <Field label="Description"><Textarea name="description" /></Field>
    </FormCard>;
}

function CreateTrainingCard({ onCreate, working }: { onCreate: (value: { title: string; provider: string | null; start_date: string | null; end_date: string | null; capacity: number | null; status: string; skills: string[]; currency: string }) => Promise<void>; working: boolean }) {
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        await onCreate({ title: String(data.get("title") || "").trim(), provider: String(data.get("provider") || "").trim() || null, start_date: String(data.get("start_date") || "") || null, end_date: String(data.get("end_date") || "") || null, capacity: Number(data.get("capacity") || 0) || null, status: "planned", skills: String(data.get("skills") || "").split(",").map((item) => item.trim()).filter(Boolean), currency: "LSL" });
        event.currentTarget.reset();
    }
    return <FormCard title="Create training programme" description="Track courses, attendance, skills and certification" onSubmit={submit} working={working}>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Programme title"><Input name="title" required /></Field><Field label="Provider"><Input name="provider" /></Field></div>
        <div className="grid gap-4 sm:grid-cols-3"><Field label="Start"><Input name="start_date" type="date" /></Field><Field label="End"><Input name="end_date" type="date" /></Field><Field label="Capacity"><Input name="capacity" type="number" min="1" /></Field></div>
        <Field label="Skills, comma separated"><Input name="skills" placeholder="Leadership, Excel, compliance" /></Field>
    </FormCard>;
}

function CreateAssetCard({ onCreate, working }: { onCreate: (value: { asset_tag: string; name: string; category: string; serial_number: string | null; condition: string; currency: string }) => Promise<void>; working: boolean }) {
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault(); const data = new FormData(event.currentTarget);
        await onCreate({ asset_tag: String(data.get("asset_tag") || "").trim().toUpperCase(), name: String(data.get("name") || "").trim(), category: String(data.get("category") || "").trim(), serial_number: String(data.get("serial_number") || "").trim() || null, condition: String(data.get("condition") || "good"), currency: "LSL" });
        event.currentTarget.reset();
    }
    return <FormCard title="Register company asset" description="Track equipment from availability through assignment, return, maintenance and retirement" onSubmit={submit} working={working}>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Asset tag"><Input name="asset_tag" required /></Field><Field label="Asset name"><Input name="name" required /></Field></div>
        <div className="grid gap-4 sm:grid-cols-3"><Field label="Category"><Input name="category" placeholder="Laptop" required /></Field><Field label="Serial number"><Input name="serial_number" /></Field><Field label="Condition"><NativeSelect name="condition" defaultValue="good"><option value="new">New</option><option value="good">Good</option><option value="fair">Fair</option><option value="damaged">Damaged</option></NativeSelect></Field></div>
    </FormCard>;
}

function FormCard({ title, description, onSubmit, working, children }: { title: string; description: string; onSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>; working: boolean; children: React.ReactNode }) {
    return <Card><CardHeader><CardTitle>{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader><CardContent><form className="space-y-4" onSubmit={(event) => void onSubmit(event)}>{children}<Button type="submit" disabled={working}>{working ? <Loader2 className="animate-spin" /> : <Plus />} Save</Button></form></CardContent></Card>;
}
