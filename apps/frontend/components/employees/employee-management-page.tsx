"use client";

import { Input } from "@/components/ui/input";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/ui/native-select";
import {
    BadgeCheck,
    BriefcaseBusiness,
    ChartNoAxesCombined,
    ContactRound,
    Landmark,
    Loader2,
    Pencil,
    Plus,
    RefreshCcw,
    Target,
    UserRoundCheck,
    Users,
} from "lucide-react";
import {
    type FormEvent,
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";
import { toast } from "@/utils/toast";

import {
    createEmployeeGoal,
    createEmployeeReview,
    listEmployees,
    updateEmployeeProfile,
} from "@/api/employees";
import {
    BANK_NAMES,
    DEFAULT_BANK_BRANCH,
    bankAccountPrefixHint,
    bankAccountValidationMessage,
    bankDetails,
    isBankName,
} from "@/lib/banking";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import {
    HR_ROLES,
    PERFORMANCE_ROLES,
    hasRole,
} from "@/types/auth";
import type {
    Employee,
    EmployeeProfilePayload,
    PerformanceGoalPayload,
    PerformanceReviewPayload,
} from "@/types/employee";
import { getErrorMessage } from "@/utils/apiError";
import { CustomDialog } from "../ui/custom-dialog";

function fullName(employee: Employee): string {
    const person = employee.user.person;
    return (
        person?.full_name ||
        [person?.first_name, person?.last_name].filter(Boolean).join(" ") ||
        employee.user.email ||
        employee.user.phone
    );
}

function initials(employee: Employee): string {
    return fullName(employee)
        .split(" ")
        .slice(0, 2)
        .map((part) => part.charAt(0))
        .join("")
        .toUpperCase();
}

function titleCase(value: string): string {
    return value
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const EMPTY_PROFILE: EmployeeProfilePayload = {
    employee_number: "",
    job_title: null,
    department: null,
    employment_type: "full_time",
    employment_status: "active",
    hire_date: null,
    probation_end_date: null,
    termination_date: null,
    reports_to_staff_id: null,
    base_salary: null,
    currency: "LSL",
    skills: [],
    target_config: {},
    bank_name: null,
    bank_account_name: null,
    bank_account_number: null,
    notes: null,
    is_manager: false,
};

function profilePayload(employee: Employee): EmployeeProfilePayload {
    if (!employee.profile) {
        return {
            ...EMPTY_PROFILE,
            employee_number: `EMP-${employee.staff_id.slice(0, 8).toUpperCase()}`,
        };
    }

    return {
        employee_number: employee.profile.employee_number,
        job_title: employee.profile.job_title,
        department: employee.profile.department,
        employment_type: employee.profile.employment_type,
        employment_status: employee.profile.employment_status,
        hire_date: employee.profile.hire_date,
        probation_end_date: employee.profile.probation_end_date,
        termination_date: employee.profile.termination_date,
        reports_to_staff_id: employee.profile.reports_to_staff_id,
        base_salary:
            employee.profile.base_salary === null
                ? null
                : Number(employee.profile.base_salary),
        currency: employee.profile.currency,
        skills: employee.profile.skills,
        target_config: employee.profile.target_config,
        bank_name: employee.profile.bank_name,
        bank_account_name: employee.profile.bank_account_name,
        // Never repopulate the editable field with the stored full account number.
        // A blank value means keep the current account unless the bank is changed.
        bank_account_number: null,
        notes: employee.profile.notes,
        is_manager: employee.profile.is_manager,
    };
}

export function EmployeeManagementPage({ embedded = false }: { embedded?: boolean }) {
    const { activeRole } = useTenant();
    const { branches, getBranchById } = useAppData();
    const canManage = hasRole(activeRole, HR_ROLES);
    const canReview = hasRole(activeRole, PERFORMANCE_ROLES);

    const [employees, setEmployees] = useState<Employee[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [branchFilter, setBranchFilter] = useState("all");
    const [statusFilter, setStatusFilter] = useState("all");
    const [selected, setSelected] = useState<Employee | null>(null);
    const [dialogMode, setDialogMode] = useState<"profile" | "goal" | "review" | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            setEmployees(await listEmployees({ active_only: false }));
        } catch (requestError: unknown) {
            setError(getErrorMessage(requestError, "Could not load employees."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    const filtered = useMemo(() => {
        const token = search.trim().toLowerCase();
        return employees.filter((employee) => {
            const values = [
                fullName(employee),
                employee.user.email,
                employee.user.phone,
                employee.profile?.employee_number,
                employee.profile?.job_title,
                employee.profile?.department,
                employee.profile?.bank_name,
                employee.role,
            ].map((value) => String(value ?? "").toLowerCase());

            return (
                (!token || values.some((value) => value.includes(token))) &&
                (branchFilter === "all" || employee.branch_id === branchFilter) &&
                (statusFilter === "all" ||
                    (statusFilter === "active" && employee.is_active) ||
                    (statusFilter === "inactive" && !employee.is_active))
            );
        });
    }, [branchFilter, employees, search, statusFilter]);

    const metrics = useMemo(
        () => ({
            total: employees.length,
            active: employees.filter((employee) => employee.is_active).length,
            completedProfiles: employees.filter((employee) => employee.profile).length,
            managers: employees.filter((employee) => employee.profile?.is_manager).length,
        }),
        [employees],
    );

    function openDialog(employee: Employee, mode: "profile" | "goal" | "review") {
        if (mode !== "profile" && !employee.profile) {
            toast.error("Complete the employee profile before assigning goals or reviews.");
            setSelected(employee);
            setDialogMode("profile");
            return;
        }
        setSelected(employee);
        setDialogMode(mode);
    }

    return (
        <main className="space-y-6">
            {!embedded && (
                <section className="relative overflow-hidden rounded-3xl border bg-card p-6 shadow-sm md:p-8">
                    <div className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
                    <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
                        <div>
                            <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                                Workforce intelligence
                            </p>
                            <h1 className="mt-2 text-3xl font-black tracking-tight">Employee management</h1>
                            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                                Maintain employment profiles, payroll banking, reporting lines, goals and performance reviews for every branch.
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={() => void load()}
                            disabled={loading}
                            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-black text-primary-foreground disabled:opacity-50"
                        >
                            <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                            Refresh employees
                        </button>
                    </div>
                </section>
            )}

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric icon={Users} label="Employees" value={metrics.total} note="All company staff memberships" />
                <Metric icon={UserRoundCheck} label="Active employees" value={metrics.active} note="Currently enabled accounts" />
                <Metric icon={BadgeCheck} label="Complete profiles" value={metrics.completedProfiles} note="Employment records configured" />
                <Metric icon={BriefcaseBusiness} label="Managers" value={metrics.managers} note="Employees marked as managers" />
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="grid gap-3 border-b p-4 md:grid-cols-[1fr_220px_180px] sm:p-5">
                    <SuggestionSearch
                        value={search}
                        onValueChange={setSearch}
                        suggestions={employees.map((employee) => ({
                            value: fullName(employee),
                            label: fullName(employee),
                            description: [
                                employee.profile?.job_title,
                                employee.profile?.department,
                                employee.profile?.bank_name,
                                getBranchById(employee.branch_id)?.name,
                            ].filter(Boolean).join(" · "),
                            keywords: [
                                employee.staff_id,
                                employee.user.email ?? "",
                                employee.user.phone,
                                employee.profile?.employee_number ?? "",
                                employee.profile?.bank_name ?? "",
                                employee.role,
                                employee.is_active ? "active" : "inactive",
                            ],
                        }))}
                        placeholder="Type an employee, role, bank, branch or department..."
                        suggestionLabel="Employees"
                        emptyMessage="No employee matches that text."
                    />
                    <NativeSelect
                        value={branchFilter}
                        onChange={(event) => setBranchFilter(event.target.value)}
                        className="h-11 rounded-xl border bg-background px-3 text-sm font-bold"
                    >
                        <option value="all">All branches</option>
                        {branches.map((branch) => (
                            <option key={branch.id} value={branch.id}>{branch.name}</option>
                        ))}
                    </NativeSelect>
                    <NativeSelect
                        value={statusFilter}
                        onChange={(event) => setStatusFilter(event.target.value)}
                        className="h-11 rounded-xl border bg-background px-3 text-sm font-bold"
                    >
                        <option value="all">All statuses</option>
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                    </NativeSelect>
                </div>

                {error && (
                    <div className="border-b border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                        {error}
                    </div>
                )}

                <div className="hidden overflow-x-auto lg:block">
                    <table className="w-full min-w-[1100px] text-sm">
                        <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                            <tr>
                                <th className="px-5 py-4">Employee</th>
                                <th className="px-4 py-4">Employment</th>
                                <th className="px-4 py-4">Branch</th>
                                <th className="px-4 py-4">Role</th>
                                <th className="px-4 py-4">Status</th>
                                <th className="px-5 py-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading && employees.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="py-20 text-center">
                                        <Loader2 className="mx-auto h-7 w-7 animate-spin text-primary" />
                                    </td>
                                </tr>
                            ) : (
                                filtered.map((employee) => (
                                    <EmployeeRow
                                        key={employee.staff_id}
                                        employee={employee}
                                        branchName={
                                            employee.branch_id
                                                ? getBranchById(employee.branch_id)?.name ?? "Unknown branch"
                                                : "Company-wide"
                                        }
                                        canManage={canManage}
                                        canReview={canReview}
                                        onOpen={openDialog}
                                    />
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                <div className="grid gap-3 p-4 lg:hidden">
                    {filtered.map((employee) => (
                        <EmployeeCard
                            key={employee.staff_id}
                            employee={employee}
                            branchName={
                                employee.branch_id
                                    ? getBranchById(employee.branch_id)?.name ?? "Unknown branch"
                                    : "Company-wide"
                            }
                            canManage={canManage}
                            canReview={canReview}
                            onOpen={openDialog}
                        />
                    ))}
                </div>

                {!loading && filtered.length === 0 && (
                    <div className="flex min-h-64 flex-col items-center justify-center p-8 text-center">
                        <ContactRound className="h-10 w-10 text-muted-foreground" />
                        <h2 className="mt-4 font-black">No employees found</h2>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Change the filters or add staff from the People & staff workspace.
                        </p>
                    </div>
                )}
            </section>

            {selected && dialogMode === "profile" && (
                <EmployeeProfileDialog
                    employee={selected}
                    employees={employees}
                    open
                    onClose={() => setDialogMode(null)}
                    onSaved={(updated) => {
                        setEmployees((current) => current.map((item) =>
                            item.staff_id === updated.staff_id ? updated : item,
                        ));
                        setDialogMode(null);
                    }}
                />
            )}
            {selected && dialogMode === "goal" && (
                <GoalDialog employee={selected} open onClose={() => setDialogMode(null)} />
            )}
            {selected && dialogMode === "review" && (
                <ReviewDialog employee={selected} open onClose={() => setDialogMode(null)} />
            )}
        </main>
    );
}

function Metric({ icon: Icon, label, value, note }: {
    icon: typeof Users;
    label: string;
    value: number;
    note: string;
}) {
    return (
        <article className="rounded-3xl border bg-card p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <p className="text-sm font-bold text-muted-foreground">{label}</p>
                    <p className="mt-2 text-3xl font-black">{value}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{note}</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                </div>
            </div>
        </article>
    );
}

function EmployeeRow({ employee, branchName, canManage, canReview, onOpen }: {
    employee: Employee;
    branchName: string;
    canManage: boolean;
    canReview: boolean;
    onOpen: (employee: Employee, mode: "profile" | "goal" | "review") => void;
}) {
    return (
        <tr className="border-t hover:bg-muted/30">
            <td className="px-5 py-4">
                <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-sm font-black text-primary">
                        {initials(employee)}
                    </div>
                    <div>
                        <p className="font-black">{fullName(employee)}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{employee.user.email ?? employee.user.phone}</p>
                    </div>
                </div>
            </td>
            <td className="px-4 py-4">
                <p className="font-bold">{employee.profile?.job_title ?? "Profile incomplete"}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                    {employee.profile?.department ?? employee.profile?.employee_number ?? "No department"}
                </p>
            </td>
            <td className="px-4 py-4 font-semibold">{branchName}</td>
            <td className="px-4 py-4">
                <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-bold">{titleCase(employee.role)}</span>
            </td>
            <td className="px-4 py-4">
                <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                    employee.is_active
                        ? "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400"
                        : "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400"
                }`}>
                    {employee.is_active ? "Active" : "Inactive"}
                </span>
            </td>
            <td className="px-5 py-4">
                <div className="flex justify-end gap-2">
                    {canManage && <ActionButton icon={Pencil} label="Profile" onClick={() => onOpen(employee, "profile")} />}
                    {canReview && (
                        <>
                            <ActionButton icon={Target} label="Goal" onClick={() => onOpen(employee, "goal")} />
                            <ActionButton icon={ChartNoAxesCombined} label="Review" onClick={() => onOpen(employee, "review")} />
                        </>
                    )}
                </div>
            </td>
        </tr>
    );
}

function EmployeeCard(props: Parameters<typeof EmployeeRow>[0]) {
    const { employee, branchName, canManage, canReview, onOpen } = props;
    return (
        <article className="rounded-2xl border p-4">
            <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-sm font-black text-primary">
                    {initials(employee)}
                </div>
                <div className="min-w-0 flex-1">
                    <p className="truncate font-black">{fullName(employee)}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{employee.profile?.job_title ?? titleCase(employee.role)}</p>
                </div>
                <span className={`h-2.5 w-2.5 rounded-full ${employee.is_active ? "bg-green-500" : "bg-red-500"}`} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-xl bg-muted/60 p-3">
                    <p className="text-muted-foreground">Branch</p>
                    <p className="mt-1 font-black">{branchName}</p>
                </div>
                <div className="rounded-xl bg-muted/60 p-3">
                    <p className="text-muted-foreground">Employee no.</p>
                    <p className="mt-1 font-black">{employee.profile?.employee_number ?? "Not set"}</p>
                </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
                {canManage && <ActionButton icon={Pencil} label="Profile" onClick={() => onOpen(employee, "profile")} />}
                {canReview && (
                    <>
                        <ActionButton icon={Target} label="Goal" onClick={() => onOpen(employee, "goal")} />
                        <ActionButton icon={ChartNoAxesCombined} label="Review" onClick={() => onOpen(employee, "review")} />
                    </>
                )}
            </div>
        </article>
    );
}

function ActionButton({ icon: Icon, label, onClick }: {
    icon: typeof Pencil;
    label: string;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border bg-background px-3 text-xs font-black transition hover:border-primary hover:text-primary"
        >
            <Icon className="h-3.5 w-3.5" />
            {label}
        </button>
    );
}

function EmployeeProfileDialog({ employee, employees, open, onClose, onSaved }: {
    employee: Employee;
    employees: Employee[];
    open: boolean;
    onClose: () => void;
    onSaved: (employee: Employee) => void;
}) {
    const [form, setForm] = useState(() => profilePayload(employee));
    const [skillsText, setSkillsText] = useState(form.skills.join(", "));
    const [submitting, setSubmitting] = useState(false);

    const storedBankName = employee.profile?.bank_name ?? null;
    const storedAccountNumber = employee.profile?.bank_account_number ?? null;
    const storedAccountLast4 = String(storedAccountNumber ?? "").replace(/\D/g, "").slice(-4);
    const selectedBankDetails = bankDetails(form.bank_name);
    const accountError = bankAccountValidationMessage(form.bank_name, form.bank_account_number);
    const legacyBankName = form.bank_name && !isBankName(form.bank_name) ? form.bank_name : null;

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();

        const selectedBank = String(form.bank_name || "").trim() || null;
        const enteredAccount = String(form.bank_account_number || "").trim() || null;
        const hasStoredAccount = Boolean(storedAccountNumber);
        const bankChanged = selectedBank !== storedBankName;

        if (enteredAccount && !selectedBank) {
            toast.warning("Select FNB, PB, STD or NB for the payroll bank account.");
            return;
        }
        if (selectedBank && (!hasStoredAccount || bankChanged) && !enteredAccount) {
            toast.warning("Enter the matching account number when adding or changing the employee bank.");
            return;
        }
        if (enteredAccount) {
            const validationMessage = bankAccountValidationMessage(selectedBank, enteredAccount);
            if (validationMessage) {
                toast.warning(validationMessage);
                return;
            }
        }

        const payload: EmployeeProfilePayload = {
            ...form,
            skills: skillsText
                .split(",")
                .map((item) => item.trim())
                .filter(Boolean),
        };

        if (hasStoredAccount && !bankChanged && !enteredAccount) {
            // Preserve the protected stored account. The backend also uses
            // exclude_unset for existing profiles as defense in depth.
            delete payload.bank_name;
            delete payload.bank_account_number;
        } else if (!selectedBank && !enteredAccount) {
            payload.bank_name = null;
            payload.bank_account_number = null;
            payload.bank_account_name = null;
        } else {
            payload.bank_name = selectedBank;
            payload.bank_account_number = enteredAccount;
        }

        setSubmitting(true);
        try {
            const updated = await updateEmployeeProfile(employee.staff_id, payload);
            toast.success("Employee profile saved.");
            onSaved(updated);
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not save employee profile."));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <CustomDialog
            open={open}
            onOpenChange={(nextOpen) => {
                if (!nextOpen && !submitting) onClose();
            }}
            title="Employee profile"
            contentClassName="max-h-[92vh] overflow-hidden p-0 sm:max-w-4xl"
        >
            <form onSubmit={submit} className="flex min-h-0 flex-col">
                <div className="min-h-0 flex-1 overflow-y-auto px-5 py-6 sm:px-7">
                    <p className="mb-5 text-sm leading-6 text-muted-foreground">
                        Configure employment and payroll banking information for{" "}
                        <span className="font-bold text-foreground">{fullName(employee)}</span>.
                    </p>

                    <div className="grid gap-4 md:grid-cols-2">
                        <Field
                            label="Employee number"
                            value={form.employee_number}
                            onChange={(value) => setForm((current) => ({ ...current, employee_number: value }))}
                            required
                        />
                        <Field
                            label="Job title"
                            value={form.job_title ?? ""}
                            onChange={(value) => setForm((current) => ({ ...current, job_title: value || null }))}
                        />
                        <Field
                            label="Department"
                            value={form.department ?? ""}
                            onChange={(value) => setForm((current) => ({ ...current, department: value || null }))}
                        />
                        <SelectField
                            label="Employment type"
                            value={form.employment_type}
                            options={["full_time", "part_time", "contract", "intern"]}
                            onChange={(value) => setForm((current) => ({ ...current, employment_type: value }))}
                        />
                        <SelectField
                            label="Employment status"
                            value={form.employment_status}
                            options={["active", "probation", "leave", "suspended", "terminated"]}
                            onChange={(value) => setForm((current) => ({ ...current, employment_status: value }))}
                        />
                        <Field
                            label="Hire date"
                            type="date"
                            value={form.hire_date ?? ""}
                            onChange={(value) => setForm((current) => ({ ...current, hire_date: value || null }))}
                        />
                        <Field
                            label="Probation end"
                            type="date"
                            value={form.probation_end_date ?? ""}
                            onChange={(value) => setForm((current) => ({ ...current, probation_end_date: value || null }))}
                        />
                        <Field
                            label="Base salary"
                            type="number"
                            value={form.base_salary?.toString() ?? ""}
                            onChange={(value) => setForm((current) => ({
                                ...current,
                                base_salary: value ? Number(value) : null,
                            }))}
                        />

                        <label className="block">
                            <span className="mb-2 block text-sm font-black">Reports to</span>
                            <NativeSelect
                                value={form.reports_to_staff_id ?? ""}
                                onChange={(event) => setForm((current) => ({
                                    ...current,
                                    reports_to_staff_id: event.target.value || null,
                                }))}
                                disabled={submitting}
                                className="h-11 w-full rounded-xl border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                <option value="">No manager</option>
                                {employees
                                    .filter((item) => item.staff_id !== employee.staff_id)
                                    .map((item) => (
                                        <option key={item.staff_id} value={item.staff_id}>{fullName(item)}</option>
                                    ))}
                            </NativeSelect>
                        </label>

                        <Field
                            label="Skills"
                            value={skillsText}
                            onChange={setSkillsText}
                            placeholder="Credit analysis, collections, Excel"
                        />

                        <div className="md:col-span-2 mt-2 rounded-2xl border bg-muted/15 p-4 sm:p-5">
                            <div className="mb-4 flex items-start gap-3">
                                <div className="rounded-xl bg-primary/10 p-2 text-primary">
                                    <Landmark className="h-5 w-5" />
                                </div>
                                <div>
                                    <p className="font-black">Payroll banking</p>
                                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                                        Only FNB, PB, STD and NB are accepted. LoanHub derives the fixed Maseru Central bank code from the selected bank and validates the account prefix before saving.
                                    </p>
                                </div>
                            </div>

                            <div className="grid gap-4 md:grid-cols-2">
                                <label>
                                    <span className="mb-2 block text-sm font-black">Bank</span>
                                    <NativeSelect
                                        value={form.bank_name ?? ""}
                                        onChange={(event) => setForm((current) => ({
                                            ...current,
                                            bank_name: event.target.value || null,
                                        }))}
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
                                    >
                                        <option value="">No payroll bank</option>
                                        {legacyBankName ? (
                                            <option value={legacyBankName}>Legacy: {legacyBankName}</option>
                                        ) : null}
                                        {BANK_NAMES.map((bankName) => (
                                            <option key={bankName} value={bankName}>{bankName}</option>
                                        ))}
                                    </NativeSelect>
                                </label>

                                <Field
                                    label="Account holder"
                                    value={form.bank_account_name ?? ""}
                                    onChange={(value) => setForm((current) => ({
                                        ...current,
                                        bank_account_name: value || null,
                                    }))}
                                    placeholder={fullName(employee)}
                                />

                                <Field
                                    label={storedAccountLast4 ? `New account number (current ••••${storedAccountLast4})` : "Account number"}
                                    type="password"
                                    value={form.bank_account_number ?? ""}
                                    onChange={(value) => setForm((current) => ({
                                        ...current,
                                        bank_account_number: value || null,
                                    }))}
                                    placeholder={storedAccountLast4 ? "Leave blank to keep current account" : "Bank account number"}
                                    description={bankAccountPrefixHint(form.bank_name)}
                                    error={accountError}
                                />

                                <div className="grid grid-cols-2 gap-3">
                                    <div className="rounded-xl border bg-background p-3">
                                        <p className="text-xs font-semibold text-muted-foreground">Branch</p>
                                        <p className="mt-1 text-sm font-black">{selectedBankDetails?.branch ?? DEFAULT_BANK_BRANCH}</p>
                                    </div>
                                    <div className="rounded-xl border bg-background p-3">
                                        <p className="text-xs font-semibold text-muted-foreground">Bank code</p>
                                        <p className="mt-1 text-sm font-black">{selectedBankDetails?.code ?? "Select bank"}</p>
                                    </div>
                                </div>
                            </div>

                            {legacyBankName ? (
                                <p className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs font-semibold text-amber-800 dark:text-amber-200">
                                    This is a historical bank value. It remains untouched until you select FNB, PB, STD or NB and enter the matching account number.
                                </p>
                            ) : null}
                        </div>

                        <label className="flex items-center gap-3 rounded-xl border p-3 md:col-span-2">
                            <Input
                                type="checkbox"
                                checked={form.is_manager}
                                onChange={(event) => setForm((current) => ({
                                    ...current,
                                    is_manager: event.target.checked,
                                }))}
                                disabled={submitting}
                                className="h-4 w-4 accent-primary"
                            />
                            <span className="text-sm font-black">This employee manages other employees</span>
                        </label>

                        <label className="md:col-span-2">
                            <span className="mb-2 block text-sm font-black">Notes</span>
                            <Textarea
                                value={form.notes ?? ""}
                                onChange={(event) => setForm((current) => ({
                                    ...current,
                                    notes: event.target.value || null,
                                }))}
                                disabled={submitting}
                                className="min-h-28 w-full resize-y rounded-xl border bg-background p-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                            />
                        </label>
                    </div>
                </div>

                <div className="flex flex-col-reverse gap-3 border-t bg-card px-5 py-4 sm:flex-row sm:justify-end sm:px-7">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={submitting}
                        className="h-11 rounded-xl border px-5 text-sm font-black transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={submitting}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pencil className="h-4 w-4" />}
                        {submitting ? "Saving profile..." : "Save profile"}
                    </button>
                </div>
            </form>
        </CustomDialog>
    );
}

function GoalDialog({ employee, open, onClose }: {
    employee: Employee;
    open: boolean;
    onClose: () => void;
}) {
    const today = new Date().toISOString().slice(0, 10);
    const end = new Date(Date.now() + 90 * 86400000).toISOString().slice(0, 10);
    const [form, setForm] = useState<PerformanceGoalPayload>({
        title: "",
        description: null,
        category: "operations",
        target_value: 100,
        current_value: 0,
        unit: "percent",
        weight: 1,
        period_start: today,
        period_end: end,
        status: "active",
    });
    const [submitting, setSubmitting] = useState(false);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setSubmitting(true);
        try {
            await createEmployeeGoal(employee.staff_id, form);
            toast.success("Performance goal assigned.");
            onClose();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not create goal."));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <CustomDialog
            open={open}
            onOpenChange={(nextOpen) => {
                if (!nextOpen && !submitting) onClose();
            }}
            title="Assign performance goal"
            contentClassName="max-h-[92vh] overflow-hidden p-0 sm:max-w-xl"
        >
            <form onSubmit={submit} className="flex min-h-0 flex-col">
                <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-6 sm:px-7">
                    <p className="text-sm leading-6 text-muted-foreground">
                        Create a measurable target for{" "}
                        <span className="font-bold text-foreground">{fullName(employee)}</span>.
                    </p>
                    <Field
                        label="Goal title"
                        value={form.title}
                        onChange={(value) => setForm((current) => ({ ...current, title: value }))}
                        required
                    />
                    <div className="grid gap-4 sm:grid-cols-2">
                        <Field
                            label="Category"
                            value={form.category}
                            onChange={(value) => setForm((current) => ({ ...current, category: value }))}
                        />
                        <Field
                            label="Unit"
                            value={form.unit}
                            onChange={(value) => setForm((current) => ({ ...current, unit: value }))}
                        />
                        <Field
                            label="Target"
                            type="number"
                            value={form.target_value.toString()}
                            onChange={(value) => setForm((current) => ({ ...current, target_value: Number(value) }))}
                        />
                        <Field
                            label="Weight"
                            type="number"
                            value={form.weight.toString()}
                            onChange={(value) => setForm((current) => ({ ...current, weight: Number(value) }))}
                        />
                        <Field
                            label="Start date"
                            type="date"
                            value={form.period_start}
                            onChange={(value) => setForm((current) => ({ ...current, period_start: value }))}
                        />
                        <Field
                            label="End date"
                            type="date"
                            value={form.period_end}
                            onChange={(value) => setForm((current) => ({ ...current, period_end: value }))}
                        />
                    </div>
                    <label className="block">
                        <span className="mb-2 block text-sm font-black">Description</span>
                        <Textarea
                            value={form.description ?? ""}
                            onChange={(event) => setForm((current) => ({
                                ...current,
                                description: event.target.value || null,
                            }))}
                            disabled={submitting}
                            className="min-h-24 w-full resize-y rounded-xl border bg-background p-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                        />
                    </label>
                </div>
                <div className="flex flex-col-reverse gap-3 border-t bg-card px-5 py-4 sm:flex-row sm:justify-end sm:px-7">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={submitting}
                        className="h-11 rounded-xl border px-5 text-sm font-black transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={submitting || !form.title.trim()}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                        {submitting ? "Assigning goal..." : "Assign goal"}
                    </button>
                </div>
            </form>
        </CustomDialog>
    );
}

function ReviewDialog({ employee, open, onClose }: {
    employee: Employee;
    open: boolean;
    onClose: () => void;
}) {
    const today = new Date().toISOString().slice(0, 10);
    const start = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10);
    const [form, setForm] = useState<PerformanceReviewPayload>({
        period_start: start,
        period_end: today,
        overall_score: 75,
        rating: "meets_expectations",
        status: "completed",
        strengths: null,
        improvements: null,
        comments: null,
        metrics: {},
    });
    const [submitting, setSubmitting] = useState(false);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setSubmitting(true);
        try {
            await createEmployeeReview(employee.staff_id, form);
            toast.success("Performance review recorded.");
            onClose();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not save review."));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <CustomDialog
            open={open}
            onOpenChange={(nextOpen) => {
                if (!nextOpen && !submitting) onClose();
            }}
            title="Performance review"
            contentClassName="max-h-[92vh] overflow-hidden p-0 sm:max-w-xl"
        >
            <form onSubmit={submit} className="flex min-h-0 flex-col">
                <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-6 sm:px-7">
                    <p className="text-sm leading-6 text-muted-foreground">
                        Record a formal performance review for{" "}
                        <span className="font-bold text-foreground">{fullName(employee)}</span>.
                    </p>
                    <div className="grid gap-4 sm:grid-cols-2">
                        <Field
                            label="Period start"
                            type="date"
                            value={form.period_start}
                            onChange={(value) => setForm((current) => ({ ...current, period_start: value }))}
                        />
                        <Field
                            label="Period end"
                            type="date"
                            value={form.period_end}
                            onChange={(value) => setForm((current) => ({ ...current, period_end: value }))}
                        />
                        <Field
                            label="Score out of 100"
                            type="number"
                            value={form.overall_score.toString()}
                            onChange={(value) => setForm((current) => ({
                                ...current,
                                overall_score: Math.min(100, Math.max(0, Number(value))),
                            }))}
                        />
                        <SelectField
                            label="Rating"
                            value={form.rating}
                            options={[
                                "exceptional",
                                "exceeds_expectations",
                                "meets_expectations",
                                "needs_improvement",
                                "unsatisfactory",
                            ]}
                            onChange={(value) => setForm((current) => ({ ...current, rating: value }))}
                        />
                    </div>
                    {(["strengths", "improvements", "comments"] as const).map((key) => (
                        <label key={key} className="block">
                            <span className="mb-2 block text-sm font-black">{titleCase(key)}</span>
                            <Textarea
                                value={form[key] ?? ""}
                                onChange={(event) => setForm((current) => ({
                                    ...current,
                                    [key]: event.target.value || null,
                                }))}
                                disabled={submitting}
                                className="min-h-20 w-full resize-y rounded-xl border bg-background p-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                            />
                        </label>
                    ))}
                </div>
                <div className="flex flex-col-reverse gap-3 border-t bg-card px-5 py-4 sm:flex-row sm:justify-end sm:px-7">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={submitting}
                        className="h-11 rounded-xl border px-5 text-sm font-black transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={submitting}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ChartNoAxesCombined className="h-4 w-4" />}
                        {submitting ? "Saving review..." : "Save review"}
                    </button>
                </div>
            </form>
        </CustomDialog>
    );
}

function Field({
    label,
    value,
    onChange,
    type = "text",
    placeholder,
    required = false,
    description,
    error,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    type?: string;
    placeholder?: string;
    required?: boolean;
    description?: string;
    error?: string | null;
}) {
    return (
        <label>
            <span className="mb-2 block text-sm font-black">{label}</span>
            <Input
                type={type}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                placeholder={placeholder}
                required={required}
                aria-invalid={error ? true : undefined}
                className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
            />
            {description ? <span className="mt-1.5 block text-xs text-muted-foreground">{description}</span> : null}
            {error ? <span className="mt-1 block text-xs font-semibold text-destructive">{error}</span> : null}
        </label>
    );
}

function SelectField({ label, value, options, onChange }: {
    label: string;
    value: string;
    options: string[];
    onChange: (value: string) => void;
}) {
    return (
        <label>
            <span className="mb-2 block text-sm font-black">{label}</span>
            <NativeSelect
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
            >
                {options.map((option) => (
                    <option key={option} value={option}>{titleCase(option)}</option>
                ))}
            </NativeSelect>
        </label>
    );
}
