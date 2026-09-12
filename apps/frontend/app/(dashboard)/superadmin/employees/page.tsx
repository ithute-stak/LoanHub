"use client";

import {
    useCallback,
    useEffect,
    useMemo,
    useState,
    type FormEvent,
    type ReactNode,
} from "react";
import {
    Pencil,
    Plus,
    RefreshCcw,
    Save,
    ShieldCheck,
    UserRoundCog,
} from "lucide-react";

import {
    createPlatformStaff,
    listPlatformStaff,
    updatePlatformStaff,
    updatePlatformStaffStatus,
} from "@/api/platformStaff";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { StickyFilterBar } from "@/components/ui/sticky-filter-bar";
import { NativeSelect } from "@/components/ui/native-select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, titleCase } from "@/lib/format";
import type { UserRole } from "@/types/auth";
import type {
    PlatformStaffAccount,
    PlatformStaffAccountPayload,
} from "@/types/platformStaff";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const roles: Array<{
    value: UserRole;
    label: string;
    description: string;
}> = [
    {
        value: "platform_admin",
        label: "Platform administrator",
        description:
            "Platform operations and administration without owner-only credential control.",
    },
    {
        value: "platform_finance",
        label: "Platform finance",
        description:
            "Cash ledgers, claims, reconciliation and financial oversight.",
    },
    {
        value: "platform_support",
        label: "Platform support",
        description: "User assistance, query handling and support workflow access.",
    },
    {
        value: "platform_auditor",
        label: "Platform auditor",
        description: "Read-only audit, payment and accounting review.",
    },
    {
        value: "platform_operations",
        label: "Platform operations",
        description: "Operational monitoring, incidents and service continuity.",
    },
    {
        value: "platform_compliance",
        label: "Platform compliance",
        description: "Compliance review, evidence and control monitoring.",
    },
];

type EmployeeForm = PlatformStaffAccountPayload & { password: string };

const emptyForm: EmployeeForm = {
    email: "",
    phone: "",
    password: "",
    first_name: "",
    middle_name: "",
    last_name: "",
    role: "platform_support",
    job_title: "",
    department: "",
    permissions: [],
    is_active: true,
};

export default function PlatformEmployeesPage() {
    const [employees, setEmployees] = useState<PlatformStaffAccount[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editing, setEditing] = useState<PlatformStaffAccount | null>(null);
    const [form, setForm] = useState<EmployeeForm>(() => ({ ...emptyForm }));
    const [permissionText, setPermissionText] = useState("");
    const [saving, setSaving] = useState(false);
    const [statusBusy, setStatusBusy] = useState<string | null>(null);
    const [search, setSearch] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const items = await listPlatformStaff();
            setEmployees(items);
        } catch (requestError: unknown) {
            setError(
                getErrorMessage(
                    requestError,
                    "Platform employees could not be loaded.",
                ),
            );
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void load();
        }, 0);

        return () => window.clearTimeout(timer);
    }, [load]);

    const filtered = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (!term) return employees;

        return employees.filter((employee) =>
            [
                employee.full_name,
                employee.email,
                employee.phone,
                employee.job_title,
                employee.department,
                employee.role,
            ]
                .filter((value): value is string => Boolean(value))
                .some((value) => value.toLowerCase().includes(term)),
        );
    }, [employees, search]);

    function handleDialogOpenChange(open: boolean) {
        setDialogOpen(open);
        if (!open) {
            setEditing(null);
            setForm({ ...emptyForm });
            setPermissionText("");
        }
    }

    function openCreate() {
        setEditing(null);
        setForm({ ...emptyForm });
        setPermissionText("");
        setDialogOpen(true);
    }

    function openEdit(employee: PlatformStaffAccount) {
        setEditing(employee);
        setForm({
            email: employee.email ?? "",
            phone: employee.phone,
            password: "",
            first_name: employee.first_name,
            middle_name: employee.middle_name ?? "",
            last_name: employee.last_name,
            role: employee.role,
            job_title: employee.job_title,
            department: employee.department ?? "",
            permissions: employee.permissions,
            is_active: employee.is_active,
        });
        setPermissionText(employee.permissions.join("\n"));
        setDialogOpen(true);
    }

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();

        const permissions = permissionText
            .split(/[\n,]/)
            .map((value) => value.trim())
            .filter(Boolean);

        if (!editing && form.password.length < 10) {
            toast.error("Enter a temporary password with at least 10 characters");
            return;
        }

        setSaving(true);
        try {
            if (editing) {
                const payload: PlatformStaffAccountPayload = {
                    email: form.email || null,
                    phone: form.phone,
                    first_name: form.first_name,
                    middle_name: form.middle_name || null,
                    last_name: form.last_name,
                    role: form.role,
                    job_title: form.job_title,
                    department: form.department || null,
                    permissions,
                    is_active: form.is_active,
                };
                await updatePlatformStaff(editing.id, payload);
                toast.success("Platform employee updated");
            } else {
                await createPlatformStaff({
                    email: form.email || null,
                    phone: form.phone,
                    password: form.password,
                    first_name: form.first_name,
                    middle_name: form.middle_name || null,
                    last_name: form.last_name,
                    role: form.role,
                    job_title: form.job_title,
                    department: form.department || null,
                    permissions,
                    is_active: form.is_active,
                });
                toast.success("Platform employee account created");
            }

            handleDialogOpenChange(false);
            await load();
        } catch (requestError: unknown) {
            toast.error(
                getErrorMessage(
                    requestError,
                    "The employee account was not saved.",
                ),
            );
        } finally {
            setSaving(false);
        }
    }

    async function toggleStatus(employee: PlatformStaffAccount) {
        setStatusBusy(employee.id);
        try {
            await updatePlatformStaffStatus(employee.id, !employee.is_active);
            toast.success(
                employee.is_active
                    ? "Employee account disabled"
                    : "Employee account enabled",
            );
            await load();
        } catch (requestError: unknown) {
            toast.error(
                getErrorMessage(
                    requestError,
                    "Account status was not changed.",
                ),
            );
        } finally {
            setStatusBusy(null);
        }
    }

    const selectedRole = roles.find((role) => role.value === form.role);

    return (
        <div className="space-y-6">
            <section className="overflow-hidden rounded-3xl border bg-gradient-to-br from-card via-card to-primary/10 p-6 shadow-sm sm:p-8">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                    <div className="max-w-3xl">
                        <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-black uppercase tracking-wide text-primary">
                            <UserRoundCog className="h-4 w-4" />
                            Platform workforce
                        </div>
                        <h1 className="text-3xl font-black">
                            Owner employee management
                        </h1>
                        <p className="mt-3 text-muted-foreground">
                            Open and maintain accounts for support, finance,
                            operations, audit, compliance and administration
                            staff. Owner-only settings remain unavailable to
                            non-owner roles.
                        </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        <LoadingButton
                            variant="outline"
                            loading={loading}
                            loadingText="Refreshing…"
                            onClick={() => void load()}
                        >
                            <RefreshCcw className="h-4 w-4" />
                            Refresh
                        </LoadingButton>
                        <Button onClick={openCreate}>
                            <Plus className="h-4 w-4" />
                            Add employee
                        </Button>
                    </div>
                </div>
            </section>

            <Alert>
                <ShieldCheck className="h-4 w-4" />
                <AlertTitle>Least-privilege accounts</AlertTitle>
                <AlertDescription>
                    Assign the employee&apos;s actual platform role. Backend role
                    checks remain authoritative.
                </AlertDescription>
            </Alert>

            {error ? (
                <Alert variant="destructive">
                    <AlertTitle>Employees unavailable</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            ) : null}

            <Card className="overflow-visible">
                <StickyFilterBar
                    ariaLabel="Platform employee search"
                    className="rounded-t-xl data-[floating=true]:rounded-2xl data-[floating=true]:border"
                >
                <CardHeader className="rounded-[inherit] bg-card">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                        <div>
                            <CardTitle>Platform employees</CardTitle>
                            <CardDescription>
                                Live accounts stored in the database. No sample
                                employees are displayed.
                            </CardDescription>
                        </div>
                        <SuggestionSearch
                            value={search}
                            onValueChange={setSearch}
                            suggestions={employees.map((employee) => ({
                                value: employee.full_name,
                                label: employee.full_name,
                                description: [employee.job_title, employee.department, titleCase(employee.role)].filter(Boolean).join(" · "),
                                keywords: [employee.id, employee.user_id, employee.email ?? "", employee.phone, employee.is_active ? "active" : "inactive"],
                            }))}
                            placeholder="Type a name, phone, role or department..."
                            suggestionLabel="Platform employees"
                            emptyMessage="No platform employee matches that text."
                            wrapperClassName="w-full sm:max-w-sm"
                        />
                    </div>
                </CardHeader>
                </StickyFilterBar>

                <CardContent className="overflow-hidden rounded-b-xl">
                    {loading ? (
                        <div className="flex min-h-48 items-center justify-center text-muted-foreground">
                            Loading employees…
                        </div>
                    ) : filtered.length === 0 ? (
                        <div className="rounded-2xl border border-dashed p-10 text-center">
                            <p className="font-black">
                                No platform employee accounts found
                            </p>
                            <p className="mt-2 text-sm text-muted-foreground">
                                Create the first support or operational account
                                when it is needed.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {filtered.map((employee) => (
                                <div
                                    key={employee.id}
                                    className="grid gap-4 rounded-2xl border p-4 lg:grid-cols-[1.3fr_1fr_1fr_auto] lg:items-center"
                                >
                                    <div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <p className="font-black">
                                                {employee.full_name}
                                            </p>
                                            <Badge
                                                variant={
                                                    employee.is_active
                                                        ? "default"
                                                        : "secondary"
                                                }
                                            >
                                                {employee.is_active
                                                    ? "Active"
                                                    : "Disabled"}
                                            </Badge>
                                        </div>
                                        <p className="mt-1 text-sm text-muted-foreground">
                                            {employee.email || employee.phone}
                                        </p>
                                    </div>

                                    <div>
                                        <p className="text-sm font-bold">
                                            {employee.job_title}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {employee.department ||
                                                "No department"}
                                        </p>
                                    </div>

                                    <div>
                                        <p className="text-sm font-bold">
                                            {titleCase(employee.role)}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            Created {formatDate(employee.created_at)}
                                        </p>
                                    </div>

                                    <div className="flex gap-2 lg:justify-end">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => openEdit(employee)}
                                        >
                                            <Pencil className="h-4 w-4" />
                                            Edit
                                        </Button>
                                        <LoadingButton
                                            size="sm"
                                            variant={
                                                employee.is_active
                                                    ? "destructive"
                                                    : "default"
                                            }
                                            loading={statusBusy === employee.id}
                                            loadingText="Saving…"
                                            onClick={() =>
                                                void toggleStatus(employee)
                                            }
                                        >
                                            {employee.is_active
                                                ? "Disable"
                                                : "Enable"}
                                        </LoadingButton>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            <CustomDialog
                open={dialogOpen}
                onOpenChange={handleDialogOpenChange}
                title={
                    editing
                        ? "Edit platform employee"
                        : "Create platform employee"
                }
                contentClassName="sm:max-w-4xl"
            >
                <form onSubmit={submit} className="space-y-5 p-6 sm:p-8">
                    <p className="text-sm text-muted-foreground">
                        Use real employee details. Passwords are accepted only
                        during account creation and are never displayed again.
                    </p>

                    <div className="grid gap-4 md:grid-cols-3">
                        <Field label="First name" required>
                            <Input
                                required
                                value={form.first_name}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        first_name: event.target.value,
                                    }))
                                }
                            />
                        </Field>
                        <Field label="Middle name">
                            <Input
                                value={form.middle_name ?? ""}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        middle_name: event.target.value,
                                    }))
                                }
                            />
                        </Field>
                        <Field label="Last name" required>
                            <Input
                                required
                                value={form.last_name}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        last_name: event.target.value,
                                    }))
                                }
                            />
                        </Field>
                        <Field label="Phone" required>
                            <Input
                                required
                                value={form.phone}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        phone: event.target.value,
                                    }))
                                }
                            />
                        </Field>
                        <Field label="Email">
                            <Input
                                type="email"
                                value={form.email ?? ""}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        email: event.target.value,
                                    }))
                                }
                            />
                        </Field>

                        {!editing ? (
                            <Field label="Temporary password" required>
                                <Input
                                    type="password"
                                    required
                                    minLength={10}
                                    value={form.password}
                                    onChange={(event) =>
                                        setForm((current) => ({
                                            ...current,
                                            password: event.target.value,
                                        }))
                                    }
                                />
                            </Field>
                        ) : null}

                        <Field label="Platform role" required>
                            <NativeSelect
                                required
                                value={form.role}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        role: event.target.value as UserRole,
                                    }))
                                }
                            >
                                {roles.map((role) => (
                                    <option
                                        key={role.value}
                                        value={role.value}
                                    >
                                        {role.label}
                                    </option>
                                ))}
                            </NativeSelect>
                        </Field>
                        <Field label="Job title" required>
                            <Input
                                required
                                value={form.job_title}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        job_title: event.target.value,
                                    }))
                                }
                            />
                        </Field>
                        <Field label="Department">
                            <Input
                                value={form.department ?? ""}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        department: event.target.value,
                                    }))
                                }
                            />
                        </Field>
                        <Field
                            label="Permission tags"
                            className="md:col-span-3"
                        >
                            <Textarea
                                placeholder="One permission tag per line"
                                value={permissionText}
                                onChange={(event) =>
                                    setPermissionText(event.target.value)
                                }
                            />
                        </Field>
                    </div>

                    <div className="rounded-2xl bg-muted/50 p-4">
                        <p className="font-bold">{selectedRole?.label}</p>
                        <p className="mt-1 text-sm text-muted-foreground">
                            {selectedRole?.description}
                        </p>
                    </div>

                    <div className="flex items-center justify-between rounded-2xl border p-4">
                        <div>
                            <p className="font-bold">Account active</p>
                            <p className="text-sm text-muted-foreground">
                                Disabled accounts cannot sign in or perform
                                platform actions.
                            </p>
                        </div>
                        <Switch
                            checked={form.is_active}
                            onCheckedChange={(checked) =>
                                setForm((current) => ({
                                    ...current,
                                    is_active: checked,
                                }))
                            }
                        />
                    </div>

                    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => handleDialogOpenChange(false)}
                        >
                            Cancel
                        </Button>
                        <LoadingButton
                            type="submit"
                            loading={saving}
                            loadingText="Saving employee…"
                        >
                            <Save className="h-4 w-4" />
                            {editing ? "Save changes" : "Create account"}
                        </LoadingButton>
                    </div>
                </form>
            </CustomDialog>
        </div>
    );
}

function Field({
    label,
    children,
    required,
    className = "",
}: {
    label: string;
    children: ReactNode;
    required?: boolean;
    className?: string;
}) {
    return (
        <div className={`space-y-2 ${className}`}>
            <Label>
                {label}
                {required ? " *" : ""}
            </Label>
            {children}
        </div>
    );
}
