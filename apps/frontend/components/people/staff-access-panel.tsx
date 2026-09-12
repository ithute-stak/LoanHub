"use client";

import { FormEvent, useMemo, useState } from "react";
import {
    BadgeCheck,
    Download,
    KeyRound,
    Loader2,
    Plus,
    ShieldCheck,
    UserRoundCog,
    Users,
} from "lucide-react";

import {
    assignCompanyStaffRole,
    createCompanyStaffAccount,
    setCompanyStaffUserStatus,
    updateCompanyStaffMember,
} from "@/api/companyStaff";
import { groupCompanyStaffByUser } from "@/components/people/staff-grouping";
import { MetricCard } from "@/components/portal/metric-card";
import { StatusBadge } from "@/components/portal/status-badge";
import { Button } from "@/components/ui/button";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { Input } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import { NativeSelect } from "@/components/ui/native-select";
import { SuggestionSearch } from "@/components/ui/suggestion-search";
import { titleCase } from "@/lib/format";
import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import {
    COMPANY_MANAGEMENT_ROLES,
    hasRole,
    type UserRole,
} from "@/types/auth";
import type { CompanyStaff } from "@/types/companyStuff";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const STAFF_ROLES: Array<{
    value: UserRole;
    label: string;
    branchRequired: boolean;
}> = [
    { value: "company_admin", label: "Company administrator", branchRequired: false },
    { value: "branch_manager", label: "Branch manager", branchRequired: true },
    { value: "loan_officer", label: "Loan officer", branchRequired: true },
    { value: "finance_officer", label: "Finance officer", branchRequired: true },
    { value: "collections_officer", label: "Collections officer", branchRequired: true },
    { value: "compliance_officer", label: "Compliance officer", branchRequired: false },
    { value: "auditor", label: "Auditor", branchRequired: false },
    { value: "customer_support", label: "Customer support", branchRequired: true },
    { value: "hr_manager", label: "HR manager", branchRequired: false },
    { value: "performance_manager", label: "Performance manager", branchRequired: false },
    { value: "risk_manager", label: "Risk manager", branchRequired: false },
    { value: "it_support", label: "IT support", branchRequired: false },
    { value: "credit_analyst", label: "Credit analyst", branchRequired: true },
    { value: "aml_cft_officer", label: "AML/CFT officer", branchRequired: false },
    { value: "treasury_officer", label: "Treasury officer", branchRequired: false },
    { value: "data_protection_officer", label: "Data-protection officer", branchRequired: false },
    { value: "regulatory_reporting_officer", label: "Regulatory reporting officer", branchRequired: false },
    { value: "operations_officer", label: "Operations officer", branchRequired: true },
    { value: "information_security_officer", label: "Information-security officer", branchRequired: false },
];

const EMPTY_FORM = {
    first_name: "",
    middle_name: "",
    last_name: "",
    phone: "",
    email: "",
    password: "",
    role: "loan_officer" as UserRole,
    branch_id: "",
    district: "",
    town_or_village: "",
};

function escapeCsvValue(value: unknown): string {
    let text = String(value ?? "").replace(/[\r\n]+/g, " ");

    // Prevent spreadsheet applications from interpreting exported staff data
    // as a formula when a name, contact, branch or role starts with one of the
    // common formula trigger characters.
    if (/^[=+\-@]/.test(text.trimStart())) {
        text = `'${text}`;
    }

    return `"${text.replaceAll('"', '""')}"`;
}

function toFileSegment(value: string): string {
    return value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "company";
}

export function StaffAccessPanel({ embedded = false }: { embedded?: boolean }) {
    const {
        companyStaff,
        currentCompany,
        branches,
        refreshAllData,
        getBranchById,
    } = useAppData();
    const { activeRole } = useTenant();
    const [search, setSearch] = useState("");
    const [roleFilter, setRoleFilter] = useState("all");
    const [showForm, setShowForm] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [assigningRole, setAssigningRole] = useState(false);
    const [roleTargetUserId, setRoleTargetUserId] = useState<string | null>(null);
    const [manageTargetUserId, setManageTargetUserId] = useState<string | null>(null);
    const [updatingMembershipId, setUpdatingMembershipId] = useState<string | null>(null);
    const [updatingPersonAccess, setUpdatingPersonAccess] = useState(false);
    const [roleForm, setRoleForm] = useState({
        role: "finance_officer" as UserRole,
        branch_id: "",
        is_primary: false,
    });
    const [form, setForm] = useState(EMPTY_FORM);
    const canManage = hasRole(activeRole, COMPANY_MANAGEMENT_ROLES);

    const staffPeople = useMemo(
        () => groupCompanyStaffByUser(companyStaff),
        [companyStaff],
    );

    const roleTarget = useMemo(
        () => staffPeople.find((person) => person.userId === roleTargetUserId) ?? null,
        [roleTargetUserId, staffPeople],
    );
    const manageTarget = useMemo(
        () => staffPeople.find((person) => person.userId === manageTargetUserId) ?? null,
        [manageTargetUserId, staffPeople],
    );

    const filteredPeople = useMemo(() => {
        const query = search.trim().toLowerCase();
        return staffPeople.filter((person) => {
            const roleText = person.memberships
                .map((membership) => titleCase(membership.role))
                .join(" ")
                .toLowerCase();
            const branchText = person.memberships
                .map((membership) => getBranchById(membership.branch_id)?.name ?? "Company-wide")
                .join(" ")
                .toLowerCase();
            const matchesSearch =
                !query ||
                person.fullName.toLowerCase().includes(query) ||
                person.contact.toLowerCase().includes(query) ||
                person.user?.phone?.toLowerCase().includes(query) ||
                roleText.includes(query) ||
                branchText.includes(query);
            const matchesRole =
                roleFilter === "all" ||
                person.memberships.some((membership) => membership.role === roleFilter);
            return matchesSearch && matchesRole;
        });
    }, [getBranchById, roleFilter, search, staffPeople]);

    const activePeopleCount = staffPeople.filter(
        (person) => person.userIsActive && person.activeMembershipCount > 0,
    ).length;
    const multiRolePeopleCount = staffPeople.filter(
        (person) => person.memberships.length > 1,
    ).length;

    const availableRoleOptions = useMemo(() => {
        if (!roleTarget) return [];
        const assignedRoles = new Set(
            roleTarget.memberships.map((membership) => membership.role),
        );
        return STAFF_ROLES.filter((option) => !assignedRoles.has(option.value));
    }, [roleTarget]);

    function openAssignRole(userId: string) {
        const person = staffPeople.find((item) => item.userId === userId);
        if (!person) return;
        const assignedRoles = new Set(
            person.memberships.map((membership) => membership.role),
        );
        const firstAvailable = STAFF_ROLES.find(
            (option) => !assignedRoles.has(option.value),
        );
        if (!firstAvailable) {
            toast.error("Every available staff role is already assigned to this person.");
            return;
        }
        setRoleForm({
            role: firstAvailable.value,
            branch_id: firstAvailable.branchRequired
                ? person.primaryMembership?.branch_id ?? ""
                : "",
            is_primary: false,
        });
        setRoleTargetUserId(userId);
    }

    function handleExportStaff() {
        if (filteredPeople.length === 0) {
            toast.error("There are no staff records to export");
            return;
        }

        const headings = [
            "Staff member",
            "Primary contact",
            "Assigned roles",
            "Access scope",
            "Verification",
            "Company access",
            "Active role assignments",
            "Total role assignments",
        ];

        const rows = filteredPeople.map((person) => {
            const assignedRoles = person.memberships
                .map((membership) => {
                    const role = titleCase(membership.role);
                    const primary = membership.is_primary ? " (Primary)" : "";
                    const inactive = membership.is_active ? "" : " (Inactive)";
                    return `${role}${primary}${inactive}`;
                })
                .join(" | ");
            const accessScope = Array.from(
                new Set(
                    person.memberships.map(
                        (membership) =>
                            getBranchById(membership.branch_id)?.name ??
                            "Company-wide",
                    ),
                ),
            ).join(" | ");
            const companyAccess =
                person.userIsActive && person.activeMembershipCount > 0
                    ? "Active"
                    : "Inactive";

            return [
                person.fullName,
                person.contact,
                assignedRoles,
                accessScope,
                person.isVerified ? "Verified" : "Pending",
                companyAccess,
                person.activeMembershipCount,
                person.memberships.length,
            ];
        });

        const csv = [headings, ...rows]
            .map((row) => row.map(escapeCsvValue).join(","))
            .join("\n");
        const blob = new Blob(["\uFEFF", csv], {
            type: "text/csv;charset=utf-8",
        });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        const companyName = currentCompany?.name ?? "company";

        anchor.href = url;
        anchor.download = `${toFileSegment(companyName)}-staff-${new Date()
            .toISOString()
            .slice(0, 10)}.csv`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);

        toast.success(`${filteredPeople.length} staff record${filteredPeople.length === 1 ? "" : "s"} exported`);
    }

    async function handleCreate(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const roleConfig = STAFF_ROLES.find((role) => role.value === form.role);
        if (roleConfig?.branchRequired && !form.branch_id) {
            toast.error("Select a branch for this staff role");
            return;
        }
        setSubmitting(true);
        try {
            await createCompanyStaffAccount({
                email: form.email.trim() || null,
                phone: form.phone.trim(),
                password: form.password,
                first_name: form.first_name.trim(),
                middle_name: form.middle_name.trim() || null,
                last_name: form.last_name.trim(),
                nationality: "Mosotho",
                district: form.district.trim() || null,
                town_or_village: form.town_or_village.trim() || null,
                branch_id: form.branch_id || null,
                role: form.role,
                is_active: true,
            });
            toast.success("Staff account created");
            setForm(EMPTY_FORM);
            setShowForm(false);
            await refreshAllData();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not create staff account"));
        } finally {
            setSubmitting(false);
        }
    }

    async function toggleMembershipStatus(membership: CompanyStaff) {
        setUpdatingMembershipId(membership.id);
        try {
            await updateCompanyStaffMember(membership.id, {
                is_active: !membership.is_active,
            });
            toast.success(
                membership.is_active
                    ? `${titleCase(membership.role)} access deactivated`
                    : `${titleCase(membership.role)} access activated`,
            );
            await refreshAllData();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not update this role"));
        } finally {
            setUpdatingMembershipId(null);
        }
    }

    async function makePrimary(membership: CompanyStaff) {
        setUpdatingMembershipId(membership.id);
        try {
            await updateCompanyStaffMember(membership.id, {
                is_primary: true,
                is_active: true,
            });
            toast.success(`${titleCase(membership.role)} is now the primary role`);
            await refreshAllData();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not change the primary role"));
        } finally {
            setUpdatingMembershipId(null);
        }
    }

    async function togglePersonAccess() {
        if (!manageTarget) return;
        const nextActive = manageTarget.activeMembershipCount === 0;
        setUpdatingPersonAccess(true);
        try {
            await setCompanyStaffUserStatus(manageTarget.userId, nextActive);
            toast.success(
                nextActive
                    ? `${manageTarget.fullName}'s company access was restored`
                    : `${manageTarget.fullName}'s company access was suspended`,
            );
            await refreshAllData();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not update company access"));
        } finally {
            setUpdatingPersonAccess(false);
        }
    }

    async function handleAssignRole(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!roleTarget || !currentCompany) return;
        const roleConfig = STAFF_ROLES.find((role) => role.value === roleForm.role);
        if (roleConfig?.branchRequired && !roleForm.branch_id) {
            toast.error("Select a branch for this role");
            return;
        }
        setAssigningRole(true);
        try {
            await assignCompanyStaffRole({
                user_id: roleTarget.userId,
                company_id: currentCompany.id,
                branch_id: roleForm.branch_id || null,
                role: roleForm.role,
                is_primary: roleForm.is_primary,
                is_active: true,
            });
            toast.success("Additional role assigned. The person remains one staff account.");
            setRoleTargetUserId(null);
            await refreshAllData();
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not assign the additional role"));
        } finally {
            setAssigningRole(false);
        }
    }

    return (
        <div className="space-y-6">
            {embedded ? (
                canManage && (
                    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <p className="text-sm font-black">Staff access actions</p>
                            <p className="mt-1 text-xs leading-5 text-muted-foreground">
                                Create a new staff login or export the staff currently shown below.
                            </p>
                        </div>
                        <div className="flex flex-col gap-2 sm:flex-row">
                            <Button
                                type="button"
                                onClick={() => setShowForm(true)}
                                className="h-11 gap-2 font-black"
                            >
                                <Plus className="h-4 w-4" /> Add staff member
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleExportStaff}
                                disabled={filteredPeople.length === 0}
                                className="h-11 gap-2 font-black"
                            >
                                <Download className="h-4 w-4" /> Export staff
                            </Button>
                        </div>
                    </section>
                )
            ) : (
                <section className="flex flex-col gap-5 rounded-3xl border bg-card p-6 shadow-sm md:flex-row md:items-end md:justify-between md:p-8">
                    <div>
                        <h1 className="text-3xl font-black">Staff and permissions</h1>
                        <p className="mt-2 text-sm text-muted-foreground">
                            One staff account may hold many roles without appearing as duplicate people.
                        </p>
                    </div>
                    {canManage && (
                        <div className="flex flex-col gap-2 sm:flex-row">
                            <Button
                                type="button"
                                onClick={() => setShowForm(true)}
                                className="h-11 gap-2 font-black"
                            >
                                <Plus className="h-4 w-4" /> Add staff member
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleExportStaff}
                                disabled={filteredPeople.length === 0}
                                className="h-11 gap-2 font-black"
                            >
                                <Download className="h-4 w-4" /> Export staff
                            </Button>
                        </div>
                    )}
                </section>
            )}

            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                    title="Staff accounts"
                    value={staffPeople.length.toLocaleString()}
                    description="Distinct people assigned to this company"
                    icon={Users}
                />
                <MetricCard
                    title="Active people"
                    value={activePeopleCount.toLocaleString()}
                    description="People with at least one active company role"
                    icon={UserRoundCog}
                />
                <MetricCard
                    title="Role assignments"
                    value={companyStaff.length.toLocaleString()}
                    description="All active and inactive role memberships"
                    icon={KeyRound}
                />
                <MetricCard
                    title="Multi-role people"
                    value={multiRolePeopleCount.toLocaleString()}
                    description="People assigned more than one company role"
                    icon={ShieldCheck}
                />
            </section>

            <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
                <div className="grid gap-3 border-b p-5 md:grid-cols-[1fr_240px]">
                    <SuggestionSearch
                        value={search}
                        onValueChange={setSearch}
                        suggestions={staffPeople.map((person) => ({
                            value: person.fullName,
                            label: person.fullName,
                            description: `${person.memberships.length} role${person.memberships.length === 1 ? "" : "s"} · ${person.contact}`,
                            keywords: [
                                person.userId,
                                person.contact,
                                person.user?.phone ?? "",
                                ...person.memberships.map((membership) => membership.role),
                                ...person.memberships.map(
                                    (membership) =>
                                        getBranchById(membership.branch_id)?.name ??
                                        "Company-wide",
                                ),
                            ],
                        }))}
                        placeholder="Type a staff name, role, branch or contact..."
                        suggestionLabel="Company people"
                        emptyMessage="No staff account matches that text."
                    />
                    <NativeSelect
                        value={roleFilter}
                        onChange={(event) => setRoleFilter(event.target.value)}
                        className="h-11 rounded-xl border bg-background px-3"
                    >
                        <option value="all">All staff roles</option>
                        {STAFF_ROLES.map((role) => (
                            <option key={role.value} value={role.value}>
                                {role.label}
                            </option>
                        ))}
                    </NativeSelect>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[1120px] text-sm">
                        <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                            <tr>
                                <th className="px-5 py-4">Staff member</th>
                                <th className="px-4 py-4">Assigned roles</th>
                                <th className="px-4 py-4">Access scope</th>
                                <th className="px-4 py-4">Verification</th>
                                <th className="px-4 py-4">Company access</th>
                                <th className="px-5 py-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredPeople.length === 0 ? (
                                <tr>
                                    <td
                                        colSpan={6}
                                        className="px-5 py-16 text-center text-muted-foreground"
                                    >
                                        No staff accounts found.
                                    </td>
                                </tr>
                            ) : (
                                filteredPeople.map((person) => {
                                    const branchNames = Array.from(
                                        new Set(
                                            person.memberships.map(
                                                (membership) =>
                                                    getBranchById(membership.branch_id)?.name ??
                                                    "Company-wide",
                                            ),
                                        ),
                                    );
                                    const accessActive =
                                        person.userIsActive &&
                                        person.activeMembershipCount > 0;
                                    const allAssignableRolesUsed = STAFF_ROLES.every((option) =>
                                        person.memberships.some(
                                            (membership) => membership.role === option.value,
                                        ),
                                    );

                                    return (
                                        <tr
                                            key={person.userId}
                                            className="border-t align-top hover:bg-muted/30"
                                        >
                                            <td className="px-5 py-4">
                                                <p className="font-black">{person.fullName}</p>
                                                <p className="mt-1 text-xs text-muted-foreground">
                                                    {person.contact}
                                                </p>
                                                <p className="mt-1 text-[11px] text-muted-foreground">
                                                    {person.memberships.length} role assignment
                                                    {person.memberships.length === 1 ? "" : "s"}
                                                </p>
                                            </td>
                                            <td className="px-4 py-4">
                                                <div className="flex max-w-md flex-wrap gap-2">
                                                    {person.memberships.map((membership) => (
                                                        <span
                                                            key={membership.id}
                                                            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-bold ${
                                                                membership.is_active
                                                                    ? "bg-primary/5 text-foreground"
                                                                    : "bg-muted text-muted-foreground line-through"
                                                            }`}
                                                        >
                                                            {titleCase(membership.role)}
                                                            {membership.is_primary && (
                                                                <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[9px] uppercase text-primary">
                                                                    Primary
                                                                </span>
                                                            )}
                                                        </span>
                                                    ))}
                                                </div>
                                            </td>
                                            <td className="px-4 py-4">
                                                <div className="space-y-1">
                                                    {branchNames.map((branchName) => (
                                                        <p key={branchName} className="text-xs font-medium">
                                                            {branchName}
                                                        </p>
                                                    ))}
                                                </div>
                                            </td>
                                            <td className="px-4 py-4">
                                                <StatusBadge
                                                    value={person.isVerified ? "verified" : "pending"}
                                                />
                                            </td>
                                            <td className="px-4 py-4">
                                                <StatusBadge
                                                    value={accessActive ? "active" : "inactive"}
                                                />
                                                <p className="mt-1 text-[11px] text-muted-foreground">
                                                    {person.activeMembershipCount} of {person.memberships.length} roles active
                                                </p>
                                            </td>
                                            <td className="px-5 py-4 text-right">
                                                <div className="flex justify-end gap-2">
                                                    {canManage && (
                                                        <button
                                                            type="button"
                                                            onClick={() => openAssignRole(person.userId)}
                                                            disabled={allAssignableRolesUsed}
                                                            className="h-9 rounded-xl border px-3 text-xs font-black text-primary disabled:cursor-not-allowed disabled:opacity-40"
                                                        >
                                                            Add role
                                                        </button>
                                                    )}
                                                    <button
                                                        type="button"
                                                        onClick={() => setManageTargetUserId(person.userId)}
                                                        className="h-9 rounded-xl border px-3 text-xs font-black"
                                                    >
                                                        Manage roles
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </section>

            {showForm && (
                <CustomDialog
                    open={showForm}
                    onOpenChange={(nextOpen) => {
                        if (!submitting) {
                            setShowForm(nextOpen);
                        }
                    }}
                    title="Create company staff account"
                    contentClassName="sm:max-w-3xl"
                >
                    <form
                        onSubmit={handleCreate}
                        className="flex min-h-0 flex-col"
                    >
                        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-6 sm:px-7">
                            <p className="mb-5 text-sm leading-6 text-muted-foreground">
                                The staff member will sign in using the
                                phone number and temporary password entered
                                here.
                            </p>

                            <div className="grid gap-4 sm:grid-cols-2">
                                <Field label="First name">
                                    <Input
                                        type="text"
                                        required
                                        autoFocus
                                        autoComplete="given-name"
                                        value={form.first_name}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                first_name:
                                                event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    />
                                </Field>

                                <Field label="Middle name">
                                    <Input
                                        type="text"
                                        autoComplete="additional-name"
                                        value={form.middle_name}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                middle_name:
                                                event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    />
                                </Field>

                                <Field label="Last name">
                                    <Input
                                        type="text"
                                        required
                                        autoComplete="family-name"
                                        value={form.last_name}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                last_name:
                                                event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    />
                                </Field>

                                <Field label="Phone">
                                    <Input
                                        type="tel"
                                        required
                                        autoComplete="tel"
                                        placeholder="+266 5800 0000"
                                        value={form.phone}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                phone: event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    />
                                </Field>

                                <Field label="Email">
                                    <Input
                                        type="email"
                                        autoComplete="email"
                                        placeholder="staff@example.com"
                                        value={form.email}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                email: event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    />
                                </Field>

                                <Field label="Temporary password">
                                    <Input
                                        type="password"
                                        required
                                        minLength={8}
                                        autoComplete="new-password"
                                        placeholder="At least 8 characters"
                                        value={form.password}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                password:
                                                event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    />
                                </Field>

                                <Field label="Role">
                                    <NativeSelect
                                        value={form.role}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                role: event.target
                                                    .value as UserRole,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        {STAFF_ROLES.map((role) => (
                                            <option
                                                key={role.value}
                                                value={role.value}
                                            >
                                                {role.label}
                                            </option>
                                        ))}
                                    </NativeSelect>
                                </Field>

                                <Field label="Assigned branch">
                                    <NativeSelect
                                        value={form.branch_id}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                branch_id:
                                                event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                        <option value="">
                                            Company-wide / no branch
                                        </option>

                                        {branches
                                            .filter(
                                                (branch) =>
                                                    branch.is_active,
                                            )
                                            .map((branch) => (
                                                <option
                                                    key={branch.id}
                                                    value={branch.id}
                                                >
                                                    {branch.name}
                                                </option>
                                            ))}
                                    </NativeSelect>
                                </Field>

                                <Field label="District">
                                    <Input
                                        type="text"
                                        autoComplete="address-level1"
                                        value={form.district}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                district:
                                                event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    />
                                </Field>

                                <Field label="Town or village">
                                    <Input
                                        type="text"
                                        autoComplete="address-level2"
                                        value={form.town_or_village}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                town_or_village:
                                                event.target.value,
                                            }))
                                        }
                                        disabled={submitting}
                                        className="h-11 w-full rounded-xl border bg-background px-3 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
                                    />
                                </Field>
                            </div>

                            <div className="mt-5 rounded-2xl border bg-muted/30 p-4">
                                <p className="text-sm font-bold">
                                    Account security
                                </p>

                                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                                    Share the temporary password privately.
                                    The staff member should change it after
                                    signing in for the first time.
                                </p>
                            </div>
                        </div>

                        <div
                            className="sticky bottom-0 flex flex-col-reverse gap-3 border-t bg-card px-5 py-4 sm:flex-row sm:justify-end sm:px-7">
                            <button
                                type="button"
                                onClick={() => setShowForm(false)}
                                disabled={submitting}
                                className="h-11 rounded-xl border px-5 text-sm font-bold transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                Cancel
                            </button>

                            <button
                                type="submit"
                                disabled={submitting}
                                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {submitting && (
                                    <Loader2 className="h-4 w-4 animate-spin"/>
                                )}

                                {submitting
                                    ? "Creating account..."
                                    : "Create account"}
                            </button>
                        </div>
                    </form>
                </CustomDialog>
            )}


            {roleTarget && (
                <CustomDialog
                    open={Boolean(roleTarget)}
                    onOpenChange={(open) => {
                        if (!open && !assigningRole) setRoleTargetUserId(null);
                    }}
                    title={`Assign another role · ${roleTarget.fullName}`}
                    contentClassName="sm:max-w-xl"
                >
                    <form onSubmit={handleAssignRole} className="p-6">
                        <p className="text-sm leading-6 text-muted-foreground">
                            This adds a role membership to the same user account. It does not create another person or another login.
                        </p>
                        <div className="mt-5 grid gap-4 sm:grid-cols-2">
                            <Field label="Additional role">
                                <NativeSelect
                                    value={roleForm.role}
                                    onChange={(event) => {
                                        const nextRole = event.target.value as UserRole;
                                        const config = STAFF_ROLES.find(
                                            (option) => option.value === nextRole,
                                        );
                                        setRoleForm((current) => ({
                                            ...current,
                                            role: nextRole,
                                            branch_id: config?.branchRequired
                                                ? current.branch_id
                                                : "",
                                        }));
                                    }}
                                    className="h-11 w-full rounded-xl border bg-background px-3"
                                >
                                    {availableRoleOptions.map((option) => (
                                        <option key={option.value} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </NativeSelect>
                            </Field>
                            <Field label="Assigned branch">
                                <NativeSelect
                                    value={roleForm.branch_id}
                                    onChange={(event) =>
                                        setRoleForm((current) => ({
                                            ...current,
                                            branch_id: event.target.value,
                                        }))
                                    }
                                    className="h-11 w-full rounded-xl border bg-background px-3"
                                >
                                    <option value="">Company-wide / no branch</option>
                                    {branches
                                        .filter((branch) => branch.is_active)
                                        .map((branch) => (
                                            <option key={branch.id} value={branch.id}>
                                                {branch.name}
                                            </option>
                                        ))}
                                </NativeSelect>
                            </Field>
                        </div>
                        <label className="mt-4 flex items-center gap-3 rounded-2xl border p-4 text-sm font-bold">
                            <Input
                                type="checkbox"
                                checked={roleForm.is_primary}
                                onChange={(event) =>
                                    setRoleForm((current) => ({
                                        ...current,
                                        is_primary: event.target.checked,
                                    }))
                                }
                                className="h-4 w-4"
                            />
                            Make this the primary role used immediately after login
                        </label>
                        <div className="mt-6 flex justify-end gap-3">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setRoleTargetUserId(null)}
                                disabled={assigningRole}
                            >
                                Cancel
                            </Button>
                            <LoadingButton
                                type="submit"
                                loading={assigningRole}
                                loadingText="Assigning role..."
                                disabled={availableRoleOptions.length === 0}
                            >
                                Assign role
                            </LoadingButton>
                        </div>
                    </form>
                </CustomDialog>
            )}

            {manageTarget && (
                <CustomDialog
                    open={Boolean(manageTarget)}
                    onOpenChange={(open) => {
                        if (!open && !updatingMembershipId && !updatingPersonAccess) {
                            setManageTargetUserId(null);
                        }
                    }}
                    title={`Manage roles · ${manageTarget.fullName}`}
                    contentClassName="sm:max-w-2xl"
                >
                    <div className="p-6">
                        <div className="flex flex-col gap-3 rounded-2xl border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                            <div>
                                <p className="font-black">One account, {manageTarget.memberships.length} role assignment{manageTarget.memberships.length === 1 ? "" : "s"}</p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                    Suspending company access disables every role for this company without deleting the user.
                                </p>
                            </div>
                            {canManage &&
                                !manageTarget.memberships.some(
                                    (membership) => membership.role === "company_owner",
                                ) && (
                                    <LoadingButton
                                        type="button"
                                        variant="outline"
                                        loading={updatingPersonAccess}
                                        loadingText="Updating..."
                                        onClick={() => void togglePersonAccess()}
                                    >
                                        {manageTarget.activeMembershipCount > 0
                                            ? "Suspend company access"
                                            : "Restore company access"}
                                    </LoadingButton>
                                )}
                        </div>

                        <div className="mt-5 space-y-3">
                            {manageTarget.memberships.map((membership) => {
                                const working = updatingMembershipId === membership.id;
                                const protectedOwner = membership.role === "company_owner";
                                return (
                                    <article
                                        key={membership.id}
                                        className="rounded-2xl border p-4"
                                    >
                                        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                                            <div>
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <p className="font-black">
                                                        {titleCase(membership.role)}
                                                    </p>
                                                    {membership.is_primary && (
                                                        <span className="rounded-full bg-primary/10 px-2 py-1 text-[10px] font-black uppercase text-primary">
                                                            Primary
                                                        </span>
                                                    )}
                                                    <StatusBadge
                                                        value={membership.is_active ? "active" : "inactive"}
                                                    />
                                                </div>
                                                <p className="mt-1 text-xs text-muted-foreground">
                                                    {getBranchById(membership.branch_id)?.name ??
                                                        "Company-wide"}
                                                </p>
                                            </div>
                                            {canManage && (
                                                <div className="flex flex-wrap gap-2">
                                                    {!membership.is_primary && (
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="outline"
                                                            disabled={working || !membership.is_active}
                                                            onClick={() => void makePrimary(membership)}
                                                        >
                                                            {working && (
                                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                            )}
                                                            Make primary
                                                        </Button>
                                                    )}
                                                    {!protectedOwner && (
                                                        <Button
                                                            type="button"
                                                            size="sm"
                                                            variant="outline"
                                                            disabled={working}
                                                            onClick={() =>
                                                                void toggleMembershipStatus(membership)
                                                            }
                                                            className={
                                                                membership.is_active
                                                                    ? "text-red-600"
                                                                    : "text-green-600"
                                                            }
                                                        >
                                                            {working && (
                                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                            )}
                                                            {membership.is_active
                                                                ? "Deactivate role"
                                                                : "Activate role"}
                                                        </Button>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </article>
                                );
                            })}
                        </div>

                        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setManageTargetUserId(null)}
                            >
                                Close
                            </Button>
                            {canManage && (
                                <Button
                                    type="button"
                                    onClick={() => {
                                        const userId = manageTarget.userId;
                                        setManageTargetUserId(null);
                                        openAssignRole(userId);
                                    }}
                                >
                                    <Plus className="h-4 w-4" /> Add another role
                                </Button>
                            )}
                        </div>
                    </div>
                </CustomDialog>
            )}
        </div>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <label className="block">
            <span className="mb-2 block text-sm font-bold">{label}</span>
            {children}
        </label>
    );
}
